# -*- coding: utf-8 -*-
"""engine.builder 纯函数测试（不触网、不依赖 streamlit）。"""

import base64

import pytest

from engine.builder import (
    MAX_TEXT_CHARS,
    build_followup_text,
    build_revise_user_text,
    build_user_text,
    clean_html,
    extract_h2_fragment,
    extract_uploaded_file,
    html_diff,
    merge_followup,
    safe_filename,
    strip_spec_comment,
    truncate,
)


# ---------------- extract_uploaded_file ----------------

def test_extract_image_returns_base64(fake_uploaded):
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    up = fake_uploaded("fig.png", raw, media_type="image/png")
    img, text = extract_uploaded_file(up)
    assert img is not None
    assert img["media_type"] == "image/png"
    assert img["data"] == base64.b64encode(raw).decode("utf-8")
    assert text == ""


def test_extract_none_returns_empty():
    assert extract_uploaded_file(None) == (None, "")


def test_extract_unknown_format(fake_uploaded):
    up = fake_uploaded("data.xlsx", b"x")
    img, text = extract_uploaded_file(up)
    assert img is None
    assert "暂不支持" in text


def test_extract_txt(fake_uploaded):
    up = fake_uploaded("note.txt", "物理\n知识".encode("utf-8"))
    img, text = extract_uploaded_file(up)
    assert img is None
    assert text == "物理\n知识"


def test_extract_docx_uses_document(fake_uploaded, monkeypatch):
    # 用假 python-docx Document 替换，避免真实依赖
    class FakeParagraph:
        def __init__(self, t):
            self.text = t

    class FakeDoc:
        def __init__(self, *args, **kwargs):
            self.paragraphs = [FakeParagraph("  "), FakeParagraph("题干第一段")]

    import engine.builder as builder_mod
    monkeypatch.setattr("docx.Document", FakeDoc, raising=False)

    up = fake_uploaded("paper.docx", b"fake")
    img, text = extract_uploaded_file(up)
    assert img is None
    assert "题干第一段" in text


def test_extract_pdf_uses_10_page_cap(fake_uploaded, monkeypatch):
    class FakePage:
        def extract_text(self):
            return "第N页内容"

    class FakeReader:
        def __init__(self, stream):
            self.pages = [FakePage() for _ in range(20)]

    import pypdf  # noqa: F401 确保可导入
    monkeypatch.setattr("pypdf.PdfReader", FakeReader, raising=False)

    up = fake_uploaded("exam.pdf", b"fake")
    img, text = extract_uploaded_file(up)
    assert img is None
    assert text.count("第N页内容") == 10  # 只读前 10 页


# ---------------- truncate ----------------

def test_truncate_over_limit():
    long_text = "x" * (MAX_TEXT_CHARS + 50)
    assert len(truncate(long_text)) == MAX_TEXT_CHARS


def test_truncate_under_limit():
    assert truncate("abc") == "abc"


# ---------------- build_user_text ----------------

def test_build_user_text_contains_all_sections():
    text = build_user_text(
        situation="极光现象",
        extracted_text="资料内容",
        question_types=["多选", "计算"],
        scale="完整试卷",
    )
    assert "【情境描述】" in text and "极光现象" in text
    assert "【用户上传资料的文字内容】" in text and "资料内容" in text
    assert "【命题要求】" in text
    assert "题型要求：多选、计算。" in text
    assert "6道大题" in text
    assert "请严格按照命题规范出题。" in text


def test_build_user_text_single_question():
    text = build_user_text(
        situation="", extracted_text="", question_types=[], scale="1道大题（3-5小题）"
    )
    assert "1道完整的大题" in text
    assert "题型要求：不限。" in text


def test_build_user_text_point_hint():
    text = build_user_text(
        situation="", extracted_text="", question_types=[],
        scale="完整试卷", point_hint="M1-A-02 匀变速直线运动的规律",
    )
    assert "【考点要求】" in text
    assert "M1-A-02" in text


def test_build_user_text_truncates_extracted():
    text = build_user_text(
        situation="", extracted_text="y" * (MAX_TEXT_CHARS + 100),
        question_types=[], scale="完整试卷",
    )
    # 截断发生在组装前
    assert "y" * (MAX_TEXT_CHARS + 1) not in text


# ---------------- build_followup_text ----------------

def test_build_followup_text_lists_points():
    text = build_followup_text(["M1-A-03 v-t图像与x-t图像", "M2-A-04 带电粒子在电场中"])
    assert "【补充命制】" in text
    assert "M1-A-03" in text and "M2-A-04" in text
    assert "<h2>" in text
    assert "不要输出完整的" in text


# ---------------- clean_html / strip_spec_comment ----------------

def test_clean_html_removes_code_fences():
    raw = "```html\n<p>你好</p>\n```"
    assert clean_html(raw) == "<p>你好</p>"


def test_clean_html_plain():
    assert clean_html("  <p>a</p>  ") == "<p>a</p>"


def test_strip_spec_comment_removes_block(sample_html_ok):
    cleaned = strip_spec_comment(clean_html(sample_html_ok))
    assert "SPEC_TABLE_JSON" not in cleaned
    assert "<table>" in cleaned
    assert "<!--" not in cleaned


def test_strip_spec_comment_no_block(sample_html_no_spec):
    cleaned = strip_spec_comment(clean_html(sample_html_no_spec))
    assert cleaned.count("<table>") == 1


# ---------------- safe_filename ----------------

def test_safe_filename_pattern():
    name = safe_filename("试卷")
    assert name.startswith("试卷_")
    parts = name.split("_", 1)[1]
    assert parts.isdigit()  # 时间戳为纯数字


# ---------------- extract_h2_fragment / merge_followup ----------------

_ORIGINAL = (
    "<!DOCTYPE html><html><head></head><body>"
    "<h1>试卷</h1>"
    "<h2>一、极光大题（18分）</h2><p>题干...</p>"
    "<h2>二、电场大题（16分）</h2><p>题干...</p>"
    '<div class="page-break"></div>'
    "<h2>参考答案</h2><p>答案...</p>"
    '<div class="page-break"></div>'
    "<h2>双向细目表</h2><table>...</table>"
    "</body></html>"
)


def test_extract_h2_fragment_single():
    frag = extract_h2_fragment("<h2>七、补充题（12分）</h2><p>新题干</p>")
    assert frag is not None
    assert frag.startswith("<h2>")
    assert "新题干" in frag


def test_extract_h2_fragment_none():
    assert extract_h2_fragment("没有标题的文本") is None
    assert extract_h2_fragment("") is None
    assert extract_h2_fragment(None) is None


def test_extract_h2_fragment_multiple_keeps_all():
    frag = extract_h2_fragment(
        "<p>开头</p><h2>七、a题</h2><p>a</p><h2>八、b题</h2><p>b</p></body></html>"
    )
    assert "七、a题" in frag and "八、b题" in frag
    assert "</body>" not in frag


def test_merge_followup_inserts_before_answers():
    followup = "<h2>七、补充大题（12分）</h2><p>新题</p>"
    merged = merge_followup(_ORIGINAL, followup)
    assert merged is not None
    # 补题位于参考答案之前
    assert merged.index("七、补充大题") < merged.index("参考答案")
    # 原卷正文与答案顺序保持
    assert merged.index("一、极光大题") < merged.index("参考答案")
    assert "双向细目表" in merged


def test_merge_followup_none_when_no_h2():
    assert merge_followup(_ORIGINAL, "纯文本没有大题") is None


def test_merge_followup_none_when_no_pagebreak():
    original_no_pb = "<h1>试卷</h1><h2>参考答案</h2>"
    assert merge_followup(original_no_pb, "<h2>七、补充题</h2><p>x</p>") is None


# ---------------- build_revise_user_text / html_diff ----------------

def test_build_revise_user_text_contains_base_and_request():
    text = build_revise_user_text("<p>原卷</p>", "把第2题改成多选")
    assert "【当前试卷（请在此基础上修改）】" in text
    assert "<p>原卷</p>" in text
    assert "【修改要求】" in text
    assert "把第2题改成多选" in text
    assert "输出修改后的完整 HTML 文档" in text


def test_html_diff_returns_comparison_table():
    diff = html_diff("<h1>旧版</h1>\n<p>题目A</p>", "<h1>新版</h1>\n<p>题目B</p>")
    assert "旧版" in diff
    assert "新版" in diff
    # HtmlDiff 会把内容 HTML 转义（<p> → &lt;p&gt;），差异字符包进 diff_chg/diff_sub span
    assert "&lt;p&gt;题目" in diff
    assert "diff_chg" in diff
    # HtmlDiff 输出是完整 HTML 表格
    assert "<table" in diff


def test_html_diff_identical_lines_no_change():
    diff = html_diff("<p>相同</p>", "<p>相同</p>")
    assert "旧版" in diff and "新版" in diff
    # 无差异时 HtmlDiff 输出 "No Differences Found"
    assert "No Differences Found" in diff
