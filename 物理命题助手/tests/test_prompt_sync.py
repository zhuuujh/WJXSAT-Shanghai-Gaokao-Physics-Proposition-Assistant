# -*- coding: utf-8 -*-
"""scripts/check_prompt_sync 的转义/提取/比较逻辑测试（不触网）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_prompt_sync import (  # noqa: E402
    compare,
    extract_index_prompt,
    import_python_prompt,
    js_cook,
    js_escape,
)


# ---------------- js 转义 / 烹饪往返 ----------------

def test_js_roundtrip_backslashes():
    text = r"物理公式用 \(...\) 或 \[...\] 表示"
    assert js_cook(js_escape(text)) == text


def test_js_roundtrip_script_tag():
    text = '   <script src="x"></script>'
    escaped = js_escape(text)
    # HTML 安全：模板字面量内不能出现裸 </script>
    assert "</script>" not in escaped
    assert "<\\/script>" in escaped
    # 烹饪后还原
    assert js_cook(escaped) == text


def test_js_roundtrip_backtick_and_dollar():
    text = "a`b${c}"
    assert js_cook(js_escape(text)) == text


def test_js_cook_known_escapes():
    assert js_cook(r"\/ \\ \n") == "/ \\ \n"
    assert js_cook(r"\(") == "("


# ---------------- 真实副本提取与一致性 ----------------

def test_extract_index_prompt_finds_content():
    text = extract_index_prompt()
    assert text is not None
    assert "命题规范" in text or "你是上海物理等级考命题专家" in text
    assert "SPEC_TABLE_JSON_START" in text  # 第 8 条已同步


def test_python_prompt_importable():
    text = import_python_prompt()
    assert "你是上海物理等级考命题专家" in text


def test_compare_matches_real_copies():
    # 当前仓库两份副本应完全一致（--fix 后）
    ok, diffs = compare(extract_index_prompt(), import_python_prompt())
    assert ok, diffs


def test_compare_detects_drift():
    # 人为制造漂移：index 副本删掉一行
    base = extract_index_prompt()
    drift = base.replace("你是上海物理等级考命题专家", "你是上海物理命题专家（改动）", 1)
    ok, diffs = compare(drift, import_python_prompt())
    assert not ok
    assert any("改动" in d or "-" in d for d in diffs)
