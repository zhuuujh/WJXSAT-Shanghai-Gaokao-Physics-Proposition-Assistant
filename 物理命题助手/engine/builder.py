# -*- coding: utf-8 -*-
"""
engine.builder —— 纯函数工具集（原 app.py 的文件解析与文本组装逻辑迁移）。

全部函数不依赖 streamlit，可单测。输入/输出均为普通 Python 类型：
- extract_uploaded_file 解析上传对象（图片→base64 / PDF / Word / 文本）
- truncate                超长截断
- build_user_text         组装发送给 AI 的用户提示
- build_followup_text     缺考点补题提示
- clean_html              去代码块包裹
- strip_spec_comment      移除细目表 JSON 注释块（保证打印稿干净）
- safe_filename           时间戳文件名
"""

import io
import base64
import time
import re

# 上传格式白名单
IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
TEXT_EXTS = {"txt", "md"}
# 提取文本截断上限（与旧版行为一致）
MAX_TEXT_CHARS = 6000
# PDF 最多读取页数
MAX_PDF_PAGES = 10

# 细目表 JSON 注释块正则（re.S 使 . 匹配换行；整块含 <!-- --> 外壳一并移除）
_SPEC_COMMENT_RE = re.compile(
    r"<!--\s*#SPEC_TABLE_JSON_START#.*?#SPEC_TABLE_JSON_END#\s*-->", re.S
)

# 代码块包裹正则（旧版清理用）
_CODE_FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```$")


def extract_uploaded_file(uploaded):
    """解析上传对象，返回 (图片base64dict|None, 提取文本)。

    参数 uploaded 需具备 .name / .getvalue() / .type（streamlit UploadedFile 即满足），
    传 None 时返回 (None, "")。
    图片 → base64；PDF → pypdf 提取文本（最多 MAX_PDF_PAGES 页）；
    docx → python-docx 提取段落文本；txt/md → utf-8 解码；其他格式 → 错误占位文本。
    """
    if uploaded is None:
        return None, ""

    name = getattr(uploaded, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    try:
        file_bytes = uploaded.getvalue()
    except AttributeError:
        return None, "[无法读取文件内容：对象缺少 getvalue()]"

    # 图片 → base64 给视觉模型
    if ext in IMAGE_EXTS:
        media_type = getattr(uploaded, "type", None) or (
            "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        )
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return {"media_type": media_type, "data": b64}, ""

    # PDF → pypdf 提取文本
    if ext == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "[未安装 pypdf，无法解析PDF]"
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages[:MAX_PDF_PAGES]:
                text += (page.extract_text() or "") + "\n"
            return None, text
        except Exception as e:
            return None, f"[PDF解析失败：{e}]"

    # Word(docx) → python-docx 提取段落文本
    if ext == "docx":
        try:
            from docx import Document
        except ImportError:
            return None, "[未安装 python-docx，无法解析Word]"
        try:
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return None, text
        except Exception as e:
            return None, f"[Word解析失败：{e}]"

    # 纯文本
    if ext in TEXT_EXTS:
        try:
            return None, file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return None, ""

    return None, "[暂不支持的格式，请用图片/PDF/Word/文本]"


def truncate(text, limit=MAX_TEXT_CHARS):
    """超长截断（保留原语义 text[:limit]）。"""
    if not text:
        return ""
    return text[:limit]


def build_user_text(situation, extracted_text, question_types, scale, point_hint=""):
    """组装发送给 AI 的用户提示。

    - situation：情境描述
    - extracted_text：上传资料提取的文本（内部已截断）
    - question_types：题型列表，如 ["多选","计算"]
    - scale：规模文案，含 "1道" 视为 1 道大题，否则完整试卷
    - point_hint：非空时追加【考点要求】段（用于缺考点补题预填）
    """
    parts = []
    if situation:
        parts.append(f"【情境描述】\n{situation}\n")
    if extracted_text:
        parts.append(f"【用户上传资料的文字内容】\n{truncate(extracted_text)}\n")
    parts.append("【命题要求】\n请根据以上情境/资料，命制上海物理等级考风格的物理试题。\n")
    parts.append(
        "题型要求：{0}。\n".format("、".join(question_types) if question_types else "不限")
    )
    parts.append(
        "规模：{0}。\n".format(
            "命制1道完整的大题（含3-5个小题）"
            if "1道" in scale
            else "命制完整6道大题的试卷"
        )
    )
    if point_hint:
        parts.append(
            "【考点要求】\n本卷需重点覆盖以下考点，请命制对应题目：\n{0}\n".format(point_hint)
        )
    parts.append("请严格按照命题规范出题。")
    return "\n".join(parts)


def build_followup_text(uncovered_points):
    """缺考点补题提示：要求 AI 仅新增命制覆盖给定考点的题目。

    uncovered_points 为考点描述字符串列表，如 ["M1-A-03 v-t图像与x-t图像"]。
    """
    lines = "\n".join("  - " + p for p in uncovered_points)
    return (
        "【补充命制】\n上一版试卷未覆盖以下必考点，请为这些考点补充命制题目：\n"
        f"{lines}\n"
        "要求：作为独立的补充大题输出（以 <h2> 开头的大题片段，标题如 七、×××（分值）），"
        "不要重复已有的题目，不要输出完整的 <!DOCTYPE html> 文档。"
    )


def extract_h2_fragment(html):
    """从补题输出中截取 <h2>… 大题片段（含多个 <h2> 时全部保留）。

    从首个 <h2 标签起，到分页符 / </body> / </html> 或文件尾截止。
    找不到 <h2> 返回 None（调用方据此回退 Tier A）。
    """
    if not html:
        return None
    m = re.search(r"<h2\b", html)
    if not m:
        return None
    start = m.start()
    end = len(html)
    for pat in ('<div class="page-break"', "</body>", "</html>"):
        i = html.find(pat, m.end())
        if i != -1 and i < end:
            end = i
    return html[start:end].rstrip()


def merge_followup(original_html, followup_html):
    """把补题片段合并进原卷：插到参考答案分页符之前。

    成功返回合并后的完整 HTML；补题无 <h2> 或找不到插入点返回 None。
    """
    fragment = extract_h2_fragment(followup_html)
    if not fragment:
        return None
    ans_idx = original_html.find("参考答案")
    if ans_idx == -1:
        return None
    head = original_html[:ans_idx]
    pb_idx = head.rfind('<div class="page-break"')
    if pb_idx == -1:
        return None
    return original_html[:pb_idx] + "\n" + fragment + "\n" + original_html[pb_idx:]


def clean_html(html):
    """去掉 ```html / ``` 代码块包裹并 strip 两端空白（旧版行为）。"""
    if not html:
        return ""
    cleaned = _CODE_FENCE_RE.sub("", html)
    return cleaned.strip()


def strip_spec_comment(html):
    """移除细目表 JSON 注释块，返回干净可打印的 HTML。

    注意：只移除标记块本身，不触碰其余内容；调用前请用 clean_html。
    """
    if not html:
        return ""
    return _SPEC_COMMENT_RE.sub("", html)


def safe_filename(prefix="试卷"):
    """返回 f'{prefix}_{时间戳}'（无扩展名、无中文，兼容 Windows）。"""
    return f"{prefix}_{int(time.time())}"


def build_revise_user_text(current_html, request):
    """改题（对话修改）用户提示：当前试卷 HTML + 修改要求。"""
    return (
        "【当前试卷（请在此基础上修改）】\n"
        f"{current_html}\n\n"
        "【修改要求】\n"
        f"{request}\n\n"
        "请输出修改后的完整 HTML 文档（保留未修改部分，末尾仍附细目表 JSON 注释块）。"
    )


def html_diff(old, new):
    """返回 difflib.HtmlDiff 对比表格 HTML（源码级新旧版比对，行级红绿标注）。"""
    import difflib

    return difflib.HtmlDiff(wrapcolumn=80).make_table(
        old.splitlines(), new.splitlines(),
        fromdesc="旧版", todesc="新版", context=True, numlines=3,
    )
