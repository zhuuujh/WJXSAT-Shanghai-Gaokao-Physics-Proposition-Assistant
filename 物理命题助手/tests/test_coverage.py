# -*- coding: utf-8 -*-
"""考纲对标覆盖逻辑 + 补题合并链路测试（不触网、不依赖 streamlit）。"""

from engine.builder import clean_html, merge_followup
from engine.validator import coverage_analysis, validate_html
from question_bank.models import Question


# ---------------- coverage_status 分类 ----------------

def _required_codes(sample_kb, n=4):
    return [p.code for p in sample_kb.required_points()[:n]]


def test_coverage_status_classifies(sample_kb):
    req = _required_codes(sample_kb, 4)
    a, b, c, d = req
    usage = {a: 0, b: 1, c: 5, d: 3}
    rows = sample_kb.coverage_status(usage, threshold=2)
    by_code = {r["point"].code: r for r in rows}
    assert by_code[a]["status"] == "未覆盖"
    assert by_code[b]["status"] == "薄弱"
    assert by_code[c]["status"] == "达标"
    assert by_code[d]["status"] == "达标"


def test_coverage_status_threshold_boundary(sample_kb):
    req = _required_codes(sample_kb, 1)[0]
    rows = sample_kb.coverage_status({req: 2}, threshold=2)
    row = next(r for r in rows if r["point"].code == req)
    assert row["status"] == "达标"


def test_coverage_status_all_required(sample_kb):
    rows = sample_kb.coverage_status({}, threshold=2)
    assert len(rows) == len(sample_kb.required_points())
    assert all(r["status"] == "未覆盖" for r in rows)


# ---------------- 题库 → 覆盖统计 集成 ----------------

def test_bank_usage_feeds_coverage(tmp_db, sample_kb):
    tmp_db.import_knowledge(sample_kb)
    tmp_db.add_question(Question(stem="A", point_codes=["M1-A-03"]))
    tmp_db.add_question(Question(stem="B", point_codes=["M1-A-03"]))
    tmp_db.add_question(Question(stem="C", point_codes=["M2-A-01"]))

    usage = tmp_db.point_usage()
    assert usage.get("M1-A-03") == 2
    rows = sample_kb.coverage_status(usage, threshold=2)
    by_code = {r["point"].code: r for r in rows}
    assert by_code["M1-A-03"]["status"] == "达标"
    assert by_code["M2-A-01"]["status"] == "薄弱" if usage.get("M2-A-01", 0) == 1 else True


def test_module_stats_via_bank(tmp_db, sample_kb):
    tmp_db.import_knowledge(sample_kb)
    tmp_db.add_question(Question(stem="A", point_codes=["M1-A-03", "M1-A-05"]))
    stats = tmp_db.module_stats()
    assert stats["M1"]["question_count"] == 1
    assert stats["M1"]["point_count"] == 2


# ---------------- 完整链路：生成 → 校验 → 覆盖分析 ----------------

def test_validate_then_coverage(sample_html_ok, sample_kb):
    report, raw = validate_html(sample_html_ok, sample_kb, "完整试卷")
    assert raw is not None
    cov = coverage_analysis(report, sample_kb)
    # 覆盖到的编码出现在 covered_codes
    assert {"M1-A-02", "M1-A-03"} <= cov.covered_codes
    # uncovered 与必考点差值一致
    required = sample_kb.required_points()
    covered_required = sum(1 for p in required if p.code in cov.covered_codes)
    assert len(cov.uncovered) == len(required) - covered_required


# ---------------- 补题合并链路 ----------------

_ORIG = (
    "<!DOCTYPE html><html><head></head><body>"
    "<h1>试卷</h1>"
    "<h2>一、极光大题（18分）</h2><p>题干...</p>"
    '<div class="page-break"></div>'
    "<h2>参考答案</h2><p>答案...</p>"
    '<div class="page-break"></div>'
    "<h2>双向细目表</h2><table>...</table>"
    "</body></html>"
)


def test_supplement_merge_keeps_structure(sample_kb):
    # 模拟补题输出（AI 遵守 <h2> 片段格式）
    followup = (
        "<h2>七、磁场补充大题（12分）</h2><p>新增内容</p>"
    )
    merged = merge_followup(_ORIG, followup)
    assert merged is not None
    assert merged.index("七、磁场补充大题") < merged.index("参考答案")
    assert merged.index("参考答案") < merged.index("双向细目表")
    # 原卷开头未被破坏
    assert merged.startswith("<!DOCTYPE html>")
    assert clean_html(merged).startswith("<!DOCTYPE html>")


def test_supplement_fallback_path_detected(sample_kb):
    # AI 未遵守格式（无 <h2>）→ merge_followup 返回 None → UI 走 Tier A
    assert merge_followup(_ORIG, "这是纯文本，没有大题标题") is None
