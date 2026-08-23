# -*- coding: utf-8 -*-
"""
ui.pages_prop —— 命题页（原 app.py 全部功能迁移）。

功能清单（迁移红线逐项保留）：
- 双提供商：Claude 视觉（图片+文本）+ DeepSeek 纯文本（忽略图片时警告）
- 文件上传全格式：图片→base64；PDF≤10页；docx；txt/md；6000字符截断
- HTML+MathJax 输出、双向细目表 <table>、@media print 分页、只输出 HTML
- 两种规模（1道大题 / 完整试卷）与题型多选
- BYOK 密钥模式；配图警告文案

新增能力：
- 生成后展示细目表结构化校验结果（engine.validator）
- 写 exam_history 出题历史（question_bank）
- 缺考点补题：完整卷生成后勾选未覆盖必考点 → 二次生成（Tier B 合并 / Tier A 独立）
- 考纲页跨页考点预填（state.point_hint）
"""

import json

import streamlit as st

from engine import prompts as prompts_mod
from engine.builder import (
    build_followup_text,
    build_user_text,
    clean_html,
    extract_uploaded_file,
    merge_followup,
    safe_filename,
    strip_spec_comment,
    truncate,
)
from engine.provider import ProviderError, generate
from engine.validator import validate_html
from question_bank.models import ExamRecord
from ui.app_state import AppState

# session_state 中保存上一次生成结果的键
_LAST_KEY = "prop_last_result"

# 补题下拉最多展示的未覆盖必考点数
_MAX_HINT_POINTS = 10

# AI 提供商 → 侧边栏 label/help（与原版一致）
_PROVIDER_LABEL = {
    "Claude": ("🔑 Claude API密钥", "在 https://console.anthropic.com 注册获取"),
    "DeepSeek": ("🔑 DeepSeek API密钥", "在 https://platform.deepseek.com 注册获取"),
}

题型选项 = ["单选", "多选", "填空", "计算", "论证/简答"]
规模选项 = ["1道大题（3-5小题）", "完整试卷（6道大题）"]


def _sidebar_widgets():
    """渲染侧边栏控件，返回参数字典（供 generate 使用）。"""
    st.sidebar.title("⚙️ 命题设置")
    st.sidebar.caption("描述一个情境，或上传题目背景资料")

    provider = st.sidebar.radio(
        "选择AI提供商",
        list(_PROVIDER_LABEL.keys()),
        help="Claude：视觉强、中文好；DeepSeek：价格便宜、国内直连",
    )
    key_label, key_help = _PROVIDER_LABEL[provider]
    api_key = st.sidebar.text_input(key_label, type="password", help=key_help)

    st.sidebar.subheader("💬 情境描述")
    situation = st.sidebar.text_area(
        "描述一个情境 / 想考的知识点",
        placeholder="例如：我想考带电粒子在磁场中的运动，请结合极光这个自然现象命制一道大题。\n\n"
        "或描述一个情景：\n'复兴号动车组从启动到进站的完整旅程'",
        height=120,
    )

    st.sidebar.subheader("📎 或上传背景资料")
    uploaded = st.sidebar.file_uploader(
        "图片 / PDF / Word / 文本",
        type=["pdf", "docx", "txt", "md", "jpg", "jpeg", "png", "gif", "webp"],
        help="图片会直接发给AI理解；PDF/Word/文本会自动提取内容",
    )

    st.sidebar.subheader("📝 题型")
    question_types = st.sidebar.multiselect(
        "选择题型（可多选）", 题型选项, default=["多选", "计算"]
    )

    scale = st.sidebar.radio("生成规模", 规模选项)
    return {
        "provider": provider.lower(),
        "api_key": api_key,
        "situation": situation,
        "uploaded": uploaded,
        "question_types": question_types,
        "scale": scale,
    }


def _render_result(result):
    """渲染生成结果：下载 / 预览 / 源码 / 校验报告 / 补题区。"""
    html_path = result["html_path"]
    html_clean = result["html_clean"]
    filename = html_path.rsplit("/", 1)[-1]

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.download_button(
            "📥 下载HTML试卷（浏览器打开后打印为PDF）",
            data=html_clean.encode("utf-8"),
            file_name=filename,
            mime="text/html",
            key="dl_" + filename,
        )
    with col2:
        st.success("✅ 已保存：" + filename)
    with col3:
        if result.get("model"):
            st.caption(f"模型：{result['model']}　|　规模：{result['scale']}")

    _render_revise_button(result)

    st.markdown("### 📖 预览")
    import streamlit.components.v1 as components

    components.html(html_clean, height=700, scrolling=True)

    with st.expander("🔧 查看源码（可复制）"):
        st.code(html_clean, language="html")

    _render_validation(result)

    if result.get("scale_is_full") and result["report"].uncovered_required:
        _render_supplement(result)


def _render_revise_button(result):
    """「对话改题」跳转按钮：把当前卷设为待修改卷并切到题目修改页。"""
    if st.button("💬 与AI对话修改此题", key="prop_revise_btn"):
        st.session_state["revise_import"] = {
            "html": result["html_clean"],
            "path": result["html_path"],
            "title": _guess_title(result["html_clean"]),
        }
        st.session_state["nav_page"] = "题目修改"
        st.rerun()


def _render_validation(result):
    """展示细目表校验结果 + 覆盖统计。"""
    report = result["report"]
    st.markdown("### 📋 细目表校验")
    if result.get("raw") is not None:
        st.caption(f"AI 输出了结构化细目表（{len(report.rows)} 行，分值合计 {report.score_total:.0f} 分）")
    else:
        st.caption("AI 未输出结构化细目表 JSON，已按可见表格尽力解析，请人工核对")

    if report.valid:
        st.success("✅ 细目表校验通过：考点编码合法、大题内不重复")
    else:
        st.error("⚠️ 细目表存在以下问题（可在下载前人工修正）：")
        for issue in report.issues:
            st.markdown(f"- {issue}")

    # 模块覆盖分布
    if report.module_counts:
        with st.expander("📊 模块覆盖分布"):
            kb = result["kb"]
            for mod in sorted(report.module_counts):
                st.markdown(f"- **{kb.module_name(mod)}**：{report.module_counts[mod]} 题")

    # 完整卷 + 有必考点未覆盖 → 提示
    if result.get("scale_is_full") and report.uncovered_required:
        n = len(report.uncovered_required)
        st.warning(
            f"本卷覆盖了必考点 {len(report.covered)} 个，仍有 **{n} 个必考点未覆盖**，"
            f"可在下方勾选后补题。"
        )


def _render_supplement(result):
    """缺考点补题区：勾选未覆盖必考点 → 二次生成。"""
    kb = result["kb"]
    uncovered = result["report"].uncovered_required[: _MAX_HINT_POINTS]
    if len(result["report"].uncovered_required) > _MAX_HINT_POINTS:
        st.caption(f"（未覆盖必考点共 {len(result['report'].uncovered_required)} 个，此处仅列出前 {_MAX_HINT_POINTS} 个）")

    st.markdown("### 🎯 缺考点补题")
    options = {f"{p.code} {p.name}": p.code for p in uncovered}
    selected_labels = st.multiselect(
        "勾选需要补题的必考点（建议每次 ≤5 个）",
        list(options.keys()),
        default=list(options.keys())[:5],
        key="prop_uncovered_select",
    )
    selected_codes = [options[k] for k in selected_labels]

    if not selected_codes:
        st.caption("未勾选任何考点，无需补题。")
        return

    col1, _ = st.columns([1, 3])
    if col1.button("🚀 为所选考点补题", key="prop_supplement_btn"):
        _run_supplement(result, selected_codes)


def _run_supplement(result, point_codes):
    """执行缺考点补题：二次生成 → 合并（Tier B）或独立输出（Tier A）。"""
    kb = result["kb"]
    descs = [f"{p.code} {p.name}" for p in kb.points_list() if p.code in point_codes]
    system = prompts_mod.命题规范
    user_text = build_followup_text(descs)

    try:
        with st.spinner("🤖 AI补充命制中，通常需要20~40秒..."):
            followup_html, model, _ = generate(
                result["provider"], result["api_key"], system, user_text
            )
        followup_html = clean_html(followup_html)
    except ProviderError as e:
        st.error(f"❌ 补题失败：{e}")
        st.stop()

    # Tier B：尝试合并进原卷
    merged = merge_followup(result["html_clean"], followup_html)
    if merged:
        filename = safe_filename("试卷_补题")
        html_path = f"{filename}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(merged)
        st.success(f"✅ 补题已合并进原卷（参考答案之前）：{html_path}")
        st.markdown("### 📖 合并后试卷预览")
        import streamlit.components.v1 as components

        components.html(merged, height=700, scrolling=True)
        st.download_button(
            "📥 下载合并后HTML",
            data=merged.encode("utf-8"),
            file_name=f"{filename}.html",
            mime="text/html",
            key="dl_sup_" + filename,
        )
        _write_history(result, merged, html_path, model, paper_type="补充题（合并）",
                       point_codes=point_codes, raw=result.get("raw"))
    else:
        # Tier A：独立补充大题文档
        filename = safe_filename("补题")
        html_path = f"{filename}.html"
        standalone = _wrap_standalone(followup_html, result)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(standalone)
        st.success(f"✅ 补题已输出为独立文档（AI未按 <h2> 片段格式输出，已自动回退）：{html_path}")
        st.markdown("### 📖 补题预览")
        import streamlit.components.v1 as components

        components.html(standalone, height=700, scrolling=True)
        st.download_button(
            "📥 下载补题HTML",
            data=standalone.encode("utf-8"),
            file_name=f"{filename}.html",
            mime="text/html",
            key="dl_sup_" + filename,
        )
        _write_history(result, standalone, html_path, model, paper_type="补充题（独立）",
                       point_codes=point_codes, raw=result.get("raw"))


def _wrap_standalone(fragment, result):
    """把补题片段包成独立 HTML 文档。"""
    title = "上海物理等级考 · 补题大题"
    return (
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>"
        "<title>补题</title>"
        "<script src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js'></script>"
        "<style>"
        "@media print { .page-break { page-break-before: always; } }"
        "body { font-family: SimSun, '宋体', serif; line-height: 1.7; padding: 24px; }"
        "h1,h2 { text-align: center; } table { border-collapse: collapse; margin: 12px auto; }"
        "td,th { border: 1px solid #444; padding: 4px 10px; }"
        "</style></head><body>"
        f"<h1>{title}</h1>"
        "<p>本页为缺考点补充命制的大题，请核对后并入原卷。</p>"
        f"{fragment}"
        "</body></html>"
    )


def _write_history(result, html_code, html_path, model, paper_type="试卷",
                   point_codes=None, raw=None):
    """写入出题历史（含细目表 JSON 与校验结论）。"""
    state = AppState.get()
    rec = ExamRecord(
        paper_title=_guess_title(html_code),
        paper_type=paper_type,
        provider=result["provider"],
        model=model,
        question_types=result["question_types"],
        situation=(result["situation"] or "")[:200],
        html_path=html_path,
        html_summary=f"len={len(html_code)}",
        spec_json=json.dumps(raw, ensure_ascii=False) if raw else "",
        spec_valid=bool(result.get("raw")) and result["report"].valid,
    )
    try:
        state.db.record_history(rec)
    except Exception as e:  # 历史记录失败不应阻断主流程
        st.warning(f"⚠️ 历史记录写入失败：{e}")


def _guess_title(html):
    """从 HTML 提取 <title> 或首个 <h1> 作为卷名。"""
    import re

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    return m.group(1).strip() if m else "未命名试卷"


def _show_point_hint(state):
    """考纲页跨页预填的考点要求提示。"""
    hint = state.point_hint
    if not hint:
        return ""
    names = []
    for code in hint:
        p = state.kb.get(code)
        names.append(f"{code} {p.name if p else ''}".strip())
    st.sidebar.warning(
        "🎯 **来自考纲页的待补考点**：\n" + "\n".join("- " + n for n in names)
        + "\n\n生成后将自动清除。"
    )
    return "\n".join(names)


def render(state: AppState):
    """命题页渲染入口。"""
    params = _sidebar_widgets()

    st.title("📐 上海物理等级考智能命题助手")
    st.caption("描述情境或上传资料，AI自动命制符合等级考风格的试卷HTML")

    st.warning(
        "⚠️ **配图说明**：AI 生成的物理示意图（受力图/电路图/图像题等）为**示意性草稿**，"
        "箭头方向、标注文字、线条粗细可能不完全准确，**请根据实际物理情境核对调整**后再使用。"
        "出题配图可参考本文件夹 `绘图参考/drawing_prompts.md`（20套按考点分类的绘图模板 + "
        "两阶段工作流：先文生图出草图、再图编辑精修），需要程序化出图可用 `绘图脚本/generate_physics_diagram.py`。"
    )

    if params["uploaded"]:
        st.sidebar.success(f"✅ 已上传：{params['uploaded'].name}")

    # 考纲页跨页预填
    point_hint = _show_point_hint(state)

    can_generate = bool(params["api_key"]) and (
        bool(params["situation"]) or bool(params["uploaded"])
    )
    if st.button("🚀 生成试卷", disabled=not can_generate):
        _run_generation(state, params, point_hint)

    # 上次结果（补题区/校验区在 rerun 后仍需渲染）
    last = st.session_state.get(_LAST_KEY)
    if last:
        _render_result(last)

    # 侧边栏使用说明
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📌 使用步骤")
    st.sidebar.markdown(
        "1. 注册Claude API：console.anthropic.com\n"
        "2. 填写API密钥\n"
        "3. 描述情境 或 上传题目背景资料\n"
        "4. 点击「生成试卷」\n"
        "5. 下载HTML，浏览器打印为PDF\n"
    )
    st.sidebar.caption(
        "提示：本版生成HTML试卷（公式用MathJax渲染），下载后在浏览器打开、Ctrl+P打印为PDF，"
        "效果与LaTeX相当。"
    )
    st.sidebar.caption(
        "📐 配图注意：AI示意图为示意性草稿，箭头方向/标注文字/线条粗细可能不准，"
        "请按实际物理情境核对调整。绘图模板见 `绘图参考/drawing_prompts.md`。"
    )


def _run_generation(state: AppState, params, point_hint=""):
    """执行一次生成并落盘 + 校验 + 写历史 + 存结果。"""
    with st.spinner("📂 正在解析资料..."):
        image_data, extracted_text = extract_uploaded_file(params["uploaded"])

    if not params["situation"] and not extracted_text and not image_data:
        st.error("❌ 请描述一个情境，或上传题目背景资料")
        st.stop()

    user_text = build_user_text(
        params["situation"],
        truncate(extracted_text),
        params["question_types"],
        params["scale"],
        point_hint=point_hint,
    )

    system = prompts_mod.命题规范
    try:
        with st.spinner("🤖 AI命题中，通常需要30~60秒..."):
            html_raw, used_model, is_image_ignored = generate(
                params["provider"], params["api_key"], system, user_text, image_data
            )
        html_code = clean_html(html_raw)
    except ProviderError as e:
        st.error(f"❌ 生成失败：{e}")
        st.stop()

    if is_image_ignored:
        st.warning("DeepSeek文本模型暂不支持图片理解，已忽略图片，请用文字补充描述。")

    # 落盘（移除细目表 JSON 注释块，保证打印稿干净）
    html_clean = strip_spec_comment(html_code)
    filename = safe_filename()
    html_path = f"{filename}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_clean)

    # 细目表校验
    report, raw = validate_html(html_code, state.kb, params["scale"])
    report.covered = {r.point_code for r in report.rows if r.point_code}

    # 写历史
    _write_history(
        {
            "provider": params["provider"],
            "question_types": params["question_types"],
            "situation": params["situation"],
            "report": report,
            "api_key": params["api_key"],
        },
        html_clean, html_path, used_model,
        paper_type="完整试卷" if "1道" not in params["scale"] else "1道大题",
        raw=raw,
    )

    # 成功提示 + 清除跨页考点
    st.success("✅ 生成成功！")
    if point_hint:
        state.clear_point_hint()

    # 存结果供补题区 rerun 使用
    st.session_state[_LAST_KEY] = {
        "html_path": html_path,
        "html_clean": html_clean,
        "report": report,
        "raw": raw,
        "kb": state.kb,
        "scale": params["scale"],
        "scale_is_full": "1道" not in params["scale"],
        "provider": params["provider"],
        "api_key": params["api_key"],
        "question_types": params["question_types"],
        "situation": params["situation"],
        "model": used_model,
    }
