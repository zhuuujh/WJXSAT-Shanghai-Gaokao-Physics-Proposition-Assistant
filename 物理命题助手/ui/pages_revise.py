# -*- coding: utf-8 -*-
"""
ui.pages_revise —— 题目修改页（对话式改题 + 新旧版比对）。

功能：
- 载入一份已生成的试卷 HTML（命题页「对话改题」跳转 / 出题历史选择 / 手动粘贴）
- 与 AI 多轮对话，在原有题目基础上做最小修改，每轮输出一个完整新版本
- 每轮展示「新旧版比对」（源码级 HTML diff，difflib.HtmlDiff 红绿标注）
- 每个版本可独立下载；全程 BYOK（密钥只存会话，不落盘）

数据流：
  engine.provider.generate_chat(provider, api_key, REVISE_SYSTEM, messages)
  首条 user 用 engine.builder.build_revise_user_text(base_html, request) 组装，
  之后每条 assistant 记录模型返回的完整 HTML，后续 user 仅传修改要求。
"""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from engine import prompts as prompts_mod
from engine.builder import (
    build_revise_user_text,
    clean_html,
    html_diff,
    safe_filename,
    strip_spec_comment,
)
from engine.provider import ProviderError, generate_chat
from ui.app_state import AppState

# session_state 键
_IMPORT_KEY = "revise_import"   # 命题页跳转带来的待修改卷 {"html","path","title"}
_SESS_KEY = "revise_session"    # 当前改题会话 dict

# 提供商控件键（widget 状态，避免与会话数据互相覆盖）
_PROVIDER_KEY = "revise_provider"
_API_KEY_KEY = "revise_api_key"


def _html_exists(rel_path: str):
    """检查落盘 HTML 是否存在（历史记录可能指向已删除文件）。"""
    p = Path(rel_path)
    return p if p.exists() else None


def _new_session(base_html, base_path, title):
    """初始化一个改题会话。"""
    st.session_state[_SESS_KEY] = {
        "base_html": base_html,
        "base_path": base_path,
        "title": title,
        "messages": [],      # 发送给 API 的完整对话（含 assistant 返回的完整 HTML）
        "versions": [],      # 历次改版：[{"request","html","path","model","prev_html"}]
        "current_html": base_html,
        "current_path": base_path,
    }


def _run_turn(sess, request):
    """执行一轮修改：调用多轮对话，落盘新版本并记录 diff 所需的前后两版。"""
    provider = st.session_state.get(_PROVIDER_KEY, "Claude").lower()
    api_key = st.session_state.get(_API_KEY_KEY, "")
    if not api_key:
        st.error("❌ 请先填写 API 密钥")
        return

    messages = list(sess["messages"])
    if not messages:
        # 首轮：把原始卷 + 修改要求一起发给 AI
        messages.append({"role": "user", "content": build_revise_user_text(sess["base_html"], request)})
    else:
        messages.append({"role": "user", "content": request})

    try:
        with st.spinner("🤖 AI 修改中，通常需要 20~40 秒..."):
            text, model = generate_chat(provider, api_key, prompts_mod.REVISE_SYSTEM, messages)
    except ProviderError as e:
        st.error(f"❌ 修改失败：{e}")
        st.stop()

    new_html = strip_spec_comment(clean_html(text))
    path = f"{safe_filename('试卷_改')}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)

    prev_html = sess["current_html"]
    sess["messages"] = messages + [{"role": "assistant", "content": text}]
    sess["versions"].append({
        "request": request,
        "html": new_html,
        "path": path,
        "model": model,
        "prev_html": prev_html,
    })
    sess["current_html"] = new_html
    sess["current_path"] = path
    st.success(f"✅ 已生成新版本：{path}")


def _render_versions(sess):
    """展示历次改版：新旧版比对 + 新版预览 + 源码。"""
    st.markdown("### 🆚 新旧版比对")
    if not sess["versions"]:
        st.caption("提交第一次修改后，这里会展示新旧版本差异。")
        return

    # 倒序展示（最新在前），最新版默认展开
    for i, v in enumerate(reversed(sess["versions"])):
        idx = len(sess["versions"]) - 1 - i
        label = f"第{idx + 1}轮　·　{v['request'][:40]}"
        with st.expander(label, expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "📥 下载此版本",
                    data=v["html"].encode("utf-8"),
                    file_name=v["path"],
                    mime="text/html",
                    key=f"rev_dl_{idx}",
                )
            with c2:
                st.caption(f"模型：{v['model']}　|　文件：{v['path']}")

            tab_diff, tab_prev, tab_src = st.tabs(["🆚 新旧版比对", "📖 新版预览", "🔧 新版源码"])
            with tab_diff:
                components.html(html_diff(v["prev_html"], v["html"]), height=520, scrolling=True)
            with tab_prev:
                components.html(v["html"], height=520, scrolling=True)
            with tab_src:
                st.code(v["html"], language="html")


def _render_session(state):
    """渲染当前改题会话：模型/密钥、当前版本预览、对话输入、版本历史。"""
    sess = st.session_state[_SESS_KEY]

    c_title, c_reset = st.columns([5, 1])
    with c_title:
        st.subheader(f"正在修改：{sess['title']}")
    with c_reset:
        if st.button("🔄 重新开始", key="revise_reset_btn"):
            del st.session_state[_SESS_KEY]
            st.rerun()

    st.sidebar.title("⚙️ 改题设置")
    provider = st.sidebar.radio(
        "选择AI提供商",
        ["Claude", "DeepSeek"],
        key=_PROVIDER_KEY,
        help="Claude：中文好、理解强；DeepSeek：价格便宜、国内直连",
    )
    st.sidebar.text_input(
        "🔑 API密钥",
        type="password",
        key=_API_KEY_KEY,
        help="与命题页一致的 API 密钥（BYOK，仅存于会话）",
    )

    st.markdown("### 📖 当前版本")
    components.html(sess["current_html"], height=500, scrolling=True)

    st.markdown("### 💬 对话修改")
    st.caption("描述要改的地方，AI 会在当前版本基础上做最小修改并输出新版本。")
    request = st.text_area(
        "修改要求",
        key="revise_request",
        placeholder="例如：把第2题改成多选，并把情境换成「复兴号动车组进站」；"
        "把第3大题的计算量降低、增加一步说理论证。",
        height=90,
    )
    if st.button("💬 提交修改", disabled=not bool(request.strip() and st.session_state.get(_API_KEY_KEY))):
        _run_turn(sess, request.strip())
        st.rerun()

    _render_versions(sess)


def _render_base_picker(state):
    """尚未载入试卷时：从出题历史选择或手动粘贴 HTML。"""
    st.info("尚未载入试卷。请从出题历史选择一份已生成的试卷，或直接粘贴 HTML 开始修改。")

    records = state.db.list_history(limit=50)
    choices, valid = [], []
    for rec in records:
        path = _html_exists(rec.html_path)
        if path:
            choices.append(f"{rec.created_at}　|　{rec.paper_title or '未命名'}　|　{rec.paper_type}")
            valid.append(path)

    if choices:
        sel = st.selectbox("从出题历史选择试卷", choices, key="revise_history_sel")
        if st.button("📄 载入所选试卷"):
            path = valid[choices.index(sel)]
            html = path.read_text(encoding="utf-8")
            _new_session(html, str(path), path.name)
            st.rerun()
    else:
        st.caption("出题历史为空或无可用 HTML，可直接粘贴下方内容。")

    st.markdown("**或直接粘贴试卷 HTML：**")
    pasted = st.text_area("粘贴试卷 HTML", key="revise_paste", height=200)
    if st.button("📄 载入粘贴的 HTML", disabled=not pasted.strip()):
        _new_session(pasted.strip(), "", "粘贴试卷")
        st.rerun()


def render(state: AppState):
    """题目修改页渲染入口。"""
    st.title("✏️ 题目修改（对话改题）")
    st.caption("在已生成试卷的基础上，与 AI 多轮对话做最小修改，并对比新旧版本")

    # 消费命题页跳转带来的待修改卷
    pending = st.session_state.get(_IMPORT_KEY)
    if pending:
        _new_session(pending["html"], pending["path"], pending["title"])
        del st.session_state[_IMPORT_KEY]

    if _SESS_KEY not in st.session_state:
        _render_base_picker(state)
    else:
        _render_session(state)
