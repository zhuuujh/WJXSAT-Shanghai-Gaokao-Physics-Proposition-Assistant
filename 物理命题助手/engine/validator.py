# -*- coding: utf-8 -*-
"""
engine.validator —— 双向细目表结构化校验。

AI 按 prompts.py【输出格式】第 8 条，会在 HTML 末尾的注释块中输出结构化细目表 JSON：
    <!--#SPEC_TABLE_JSON_START#{...}#SPEC_TABLE_JSON_END#-->
本模块提取该 JSON，对照考点库检查：
1. 合法性   —— point_code 是否存在于考点库
2. 重复性   —— 同一大题内考点是否重复（违反"大题内考点不重复"）
3. 覆盖度   —— 完整试卷是否覆盖了全部必考点（is_required）
4. 分值合计 —— 与满分对照
5. 难度顺序 —— 大题内小题是否由易到难

AI 未输出 JSON 时，降级用 fallback_parse_table 从可见 <table> 尽力解析并显式警告。
"""

import json
import re
from dataclasses import dataclass, field

from .prompts import SPEC_JSON_START, SPEC_JSON_END

# 提取细目表 JSON 的正则（兼容有无 HTML 注释外壳）
_SPEC_JSON_RE = re.compile(
    re.escape(SPEC_JSON_START) + r"(.*?)" + re.escape(SPEC_JSON_END), re.S
)

# 难度 → 权重（用于"由易到难"检查）
_DIFF_WEIGHT = {"易": 1, "中": 2, "较难": 3, "难": 3, "综合": 4}

# 可见表格表头别名映射（fallback 用）
_HEADER_ALIAS = {
    "大题": "big", "小题": "sub", "考点": "point",
    "教材来源": "textbook", "难度": "difficulty", "分值": "score",
}


@dataclass
class SpecRow:
    """细目表一行。"""

    sub: str
    point_code: str = ""
    point_name: str = ""
    textbook_source: str = ""
    difficulty: str = ""
    score: float = 0.0

    @property
    def big(self):
        """大题号（sub 首段）。"""
        return str(self.sub).split("-")[0].split(".")[0].strip()


@dataclass
class ValidationReport:
    """细目表校验结果。"""

    valid: bool = True
    rows: list = field(default_factory=list)
    issues: list = field(default_factory=list)       # 人类可读问题清单
    unknown_codes: list = field(default_factory=list)
    duplicate_codes: list = field(default_factory=list)
    uncovered_required: list = field(default_factory=list)
    score_total: float = 0.0
    module_counts: dict = field(default_factory=dict)


@dataclass
class CoverageReport:
    """覆盖分析结果（供缺考点补题）。"""

    uncovered: list = field(default_factory=list)    # 未覆盖必考点 (KnowledgePoint)
    covered_codes: set = field(default_factory=set)
    module_counts: dict = field(default_factory=dict)


# ---------------- 提取 ----------------

def extract_spec_json(html):
    """从 HTML 提取细目表 JSON dict；未找到或解析失败返回 None。"""
    if not html:
        return None
    m = _SPEC_JSON_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def parse_rows(raw):
    """细目表原始 dict → SpecRow 列表（容错跳过非法行）。"""
    rows = []
    for item in (raw or {}).get("rows", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(SpecRow(
                sub=str(item.get("sub", "")),
                point_code=str(item.get("point_code", "") or ""),
                point_name=str(item.get("point_name", "") or ""),
                textbook_source=str(item.get("textbook_source", "") or ""),
                difficulty=str(item.get("difficulty", "") or ""),
                score=float(item.get("score", 0) or 0),
            ))
        except (TypeError, ValueError):
            continue
    return rows


# ---------------- 校验 ----------------

def _sub_issue(label, msg):
    return f"[{label}] {msg}"


def validate_spec(raw, kb, scale):
    """校验细目表 JSON，返回 ValidationReport。scale 为规模文案。"""
    rows = parse_rows(raw)
    report = ValidationReport(rows=rows)
    is_full = "1道" not in scale  # 完整试卷

    # 1. 合法性：编码不存在于考点库
    for r in rows:
        if r.point_code and kb.get(r.point_code) is None:
            report.unknown_codes.append(r.point_code)

    # 2. 重复性：同一大题内考点重复
    seen = {}
    for r in rows:
        if r.point_code:
            seen.setdefault(r.big, []).append(r.point_code)
    for big, codes in seen.items():
        dupes = {c for c in codes if codes.count(c) > 1}
        for c in sorted(dupes):
            report.duplicate_codes.append(f"{big}:{c}")

    # 3. 覆盖度：完整试卷对照必考点
    covered = {r.point_code for r in rows if r.point_code}
    if is_full:
        for p in kb.required_points():
            if p.code not in covered:
                report.uncovered_required.append(p)

    # 4. 分值合计
    report.score_total = sum(r.score for r in rows)
    declared_total = raw.get("score_total")
    if declared_total is not None:
        try:
            target = float(declared_total)
            if abs(report.score_total - target) > 0.01:
                report.issues.append(_sub_issue(
                    "分值", f"行分值合计 {report.score_total:.1f} 与声明的 {target:.1f} 不一致"))
        except (TypeError, ValueError):
            pass
    if is_full and abs(report.score_total - 100) > 0.01:
        report.issues.append(_sub_issue(
            "分值", f"完整试卷分值合计 {report.score_total:.1f}，应为 100"))

    # 5. 难度顺序：大题内由易到难
    for big in sorted({r.big for r in rows}):
        group = sorted(
            (r for r in rows if r.big == big),
            key=lambda x: _sub_sort_key(x.sub),
        )
        prev = 0
        for r in group:
            w = _DIFF_WEIGHT.get(r.difficulty, 0)
            if w and w < prev:
                report.issues.append(_sub_issue(
                    "难度", f"大题 {big} 小题 {r.sub} 难度回退（{r.difficulty}）"))
                break
            if w:
                prev = w

    # 统计模块分布
    for r in rows:
        p = kb.get(r.point_code) if r.point_code else None
        mod = p.module if p else "未知"
        report.module_counts[mod] = report.module_counts.get(mod, 0) + 1

    report.valid = not (report.unknown_codes or report.duplicate_codes)
    _fill_issues(report, kb)
    return report


def _sub_sort_key(sub):
    """把 '1-10' 排到 '1-2' 之后。"""
    parts = str(sub).replace("（", "-").replace("）", "-").replace("(", "-").replace(")", "-")
    nums = re.findall(r"\d+", parts)
    return [int(n) for n in nums] if nums else [0]


def _fill_issues(report, kb):
    """把结构化缺陷转成人类可读问题清单。"""
    for c in report.unknown_codes:
        report.issues.append(_sub_issue(
            "考点非法", f"考点编码 {c} 不在考点库中，请核对或补充考点库"))
    for d in report.duplicate_codes:
        big, code = d.split(":", 1)
        p = kb.get(code)
        name = p.name if p else code
        report.issues.append(_sub_issue(
            "考点重复", f"大题 {big} 内考点重复：{code} {name}"))
    for p in report.uncovered_required:
        report.issues.append(_sub_issue(
            "覆盖不足", f"未覆盖必考点 {p.code} {p.name}（{kb.module_name(p.module)}）"))


# ---------------- 降级解析（AI 未输出 JSON） ----------------

def fallback_parse_table(html):
    """从可见 <table> 中尽力解析细目表行（表头含"考点"的表）。"""
    table_m = re.search(r"<table[^>]*>(.*?)</table>", html, re.S)
    if not table_m:
        return []
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_m.group(1), re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if not cells:
            continue
        # 表头行：尝试定位列
        if any(_HEADER_ALIAS.get(c, "") == "point" for c in cells):
            _last_header = cells
            continue
        rows.append(cells)
    return _parse_table_by_header(rows)


def _parse_table_by_header(cell_rows):
    """根据表头映射解析行（尽力而为）。"""
    # 简单启发：识别包含"大题/小题/考点"语义的行
    parsed = []
    for cells in cell_rows:
        if len(cells) < 3:
            continue
        # 跳过明显非细目表行
        joined = "".join(cells)
        if "考点" not in joined and "总分" in joined:
            continue
        sub = cells[0] if cells else ""
        # 尝试提取 大题号-小题号
        big, small = _extract_big_small(cells)
        point = _first_containing(cells, "考点") or _safe_get(cells, 2)
        if not point:
            continue
        parsed.append(SpecRow(
            sub=f"{big}-{small}" if small else big,
            point_name=point,
            difficulty=_first_matching(cells, _DIFF_WEIGHT),
            score=_first_float(cells),
        ))
    return parsed


def _extract_big_small(cells):
    first = str(cells[0])
    m = re.search(r"([一二三四五六七八九十]|1|2|3|4|5|6|7)\D*(\d+)", first)
    if m:
        return m.group(1), m.group(2)
    return first, ""


def _first_containing(cells, kw):
    for c in cells:
        if kw in c:
            return c
    return None


def _first_matching(cells, mapping):
    for c in cells:
        if c in mapping:
            return c
    return None


def _first_float(cells):
    for c in cells:
        try:
            return float(c)
        except (TypeError, ValueError):
            continue
    return 0.0


def _safe_get(cells, idx):
    return cells[idx] if len(cells) > idx else ""


# ---------------- 覆盖分析 ----------------

def coverage_analysis(report, kb):
    """基于校验报告做覆盖分析，返回 CoverageReport（供缺考点补题）。"""
    covered = {r.point_code for r in report.rows if r.point_code}
    uncovered = [p for p in kb.required_points() if p.code not in covered]
    return CoverageReport(
        uncovered=uncovered,
        covered_codes=covered,
        module_counts=dict(report.module_counts),
    )


# ---------------- 对外统一入口 ----------------

def validate_html(html, kb, scale):
    """校验完整 HTML。返回 (ValidationReport, raw_json|None)。

    raw_json 为 None 表示 AI 未输出结构化细目表（已降级表格解析并在 issues 中警告）。
    """
    raw = extract_spec_json(html)
    if raw is not None:
        report = validate_spec(raw, kb, scale)
        return report, raw

    # 降级：尽力解析可见表格
    rows = fallback_parse_table(html)
    report = ValidationReport(rows=rows)
    report.issues.append(_sub_issue(
        "降级", "AI 未输出结构化细目表 JSON，已按可见表格尽力解析，请人工核对"))
    report.valid = False
    return report, None
