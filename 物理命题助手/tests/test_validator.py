# -*- coding: utf-8 -*-
"""engine.validator 双向细目表校验测试（不触网）。"""

import pytest

from engine.validator import (
    CoverageReport,
    ValidationReport,
    coverage_analysis,
    extract_spec_json,
    fallback_parse_table,
    parse_rows,
    validate_html,
    validate_spec,
)

# 构造一份含难度回退的细目表 JSON
_BACKTRACK_SPEC = (
    "#SPEC_TABLE_JSON_START#\n"
    '{"rows":['
    '{"sub":"1-1","point_code":"M1-A-02","point_name":"x","textbook_source":"b","difficulty":"中","score":4},'
    '{"sub":"1-2","point_code":"M1-A-03","point_name":"y","textbook_source":"b","difficulty":"易","score":6}'
    '],"score_total":10}\n'
    "#SPEC_TABLE_JSON_END#"
)


# ---------------- 提取 ----------------

def test_extract_spec_json_ok(sample_html_ok):
    raw = extract_spec_json(sample_html_ok)
    assert isinstance(raw, dict)
    assert "rows" in raw
    assert len(raw["rows"]) == 2


def test_extract_spec_json_none(sample_html_no_spec):
    assert extract_spec_json(sample_html_no_spec) is None


def test_extract_spec_json_invalid():
    html = "<!--#SPEC_TABLE_JSON_START#{not json#SPEC_TABLE_JSON_END#-->"
    assert extract_spec_json(html) is None


def test_extract_spec_json_empty():
    assert extract_spec_json("") is None
    assert extract_spec_json(None) is None


# ---------------- 解析 ----------------

def test_parse_rows_skips_bad_items():
    rows = parse_rows({"rows": [
        {"sub": "1-1", "point_code": "M1-A-02", "score": 4},
        "not-a-dict",
        {"sub": "1-2", "point_code": "M1-A-03", "score": "6"},
        {"sub": "1-3", "score": "bad-float"},   # score 转换失败 → 整行跳过
    ]})
    assert len(rows) == 2
    assert rows[0].point_code == "M1-A-02"
    assert rows[1].score == 6.0


def test_parse_rows_empty():
    assert parse_rows(None) == []
    assert parse_rows({}) == []


# ---------------- 校验 ----------------

def test_validate_ok_small_scale(sample_html_ok, sample_kb):
    raw = extract_spec_json(sample_html_ok)
    report = validate_spec(raw, sample_kb, "1道大题")
    assert report.valid is True
    assert report.issues == []
    assert report.rows[0].big == "1"


def test_validate_bad_unknown_and_duplicate(sample_html_bad, sample_kb):
    raw = extract_spec_json(sample_html_bad)
    report = validate_spec(raw, sample_kb, "1道大题")
    assert report.valid is False
    assert "M1-Z-99" in report.unknown_codes
    assert any("M1-A-02" in d for d in report.duplicate_codes)
    assert any("考点非法" in i for i in report.issues)
    assert any("考点重复" in i for i in report.issues)


def test_validate_full_scale_detects_uncovered(sample_html_ok, sample_kb):
    raw = extract_spec_json(sample_html_ok)
    report = validate_spec(raw, sample_kb, "完整试卷")
    # 完整卷只覆盖 2 个必考点，其余必考点应列为未覆盖
    assert len(report.uncovered_required) > 10
    assert any("覆盖不足" in i for i in report.issues)


def test_validate_score_total_mismatch(sample_html_bad, sample_kb):
    raw = extract_spec_json(sample_html_bad)
    report = validate_spec(raw, sample_kb, "完整试卷")
    # 行合计 18，但完整卷要求 100
    assert any("分值" in i for i in report.issues)


def test_validate_difficulty_backtrack(sample_kb):
    raw = extract_spec_json(
        "<html></html><!--" + _BACKTRACK_SPEC + "-->"
    )
    report = validate_spec(raw, sample_kb, "1道大题")
    assert any("难度回退" in i for i in report.issues)


def test_validate_module_counts(sample_html_ok, sample_kb):
    raw = extract_spec_json(sample_html_ok)
    report = validate_spec(raw, sample_kb, "1道大题")
    assert report.module_counts.get("M1", 0) == 2


# ---------------- 统一入口 + 降级 ----------------

def test_validate_html_uses_json(sample_html_ok, sample_kb):
    report, raw = validate_html(sample_html_ok, sample_kb, "1道大题")
    assert raw is not None
    assert report.valid is True


def test_validate_html_fallback(sample_html_no_spec, sample_kb):
    report, raw = validate_html(sample_html_no_spec, sample_kb, "1道大题")
    assert raw is None
    assert report.valid is False
    assert any("降级" in i for i in report.issues)


def test_fallback_parse_table_finds_rows(sample_html_ok, sample_kb):
    # 从可见 <table> 解析（忽略 JSON 注释）
    rows = fallback_parse_table(sample_html_ok)
    assert len(rows) >= 1
    assert "匀变速" in rows[0].point_name


def test_fallback_parse_table_empty():
    assert fallback_parse_table("<p>无表格</p>") == []


# ---------------- 覆盖分析 ----------------

def test_coverage_analysis(sample_html_ok, sample_kb):
    report, _ = validate_html(sample_html_ok, sample_kb, "完整试卷")
    cov = coverage_analysis(report, sample_kb)
    assert isinstance(cov, CoverageReport)
    assert "M1-A-02" in cov.covered_codes
    required = sample_kb.required_points()
    covered_required = sum(1 for p in required if p.code in cov.covered_codes)
    assert len(cov.uncovered) == len(required) - covered_required
    # uncovered 全部为必考点
    assert all(p.is_required for p in cov.uncovered)
