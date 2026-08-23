# -*- coding: utf-8 -*-
"""
ui.pages_history —— 出题历史页。

列出每次生成（试卷 / 补题）的记录：卷名 / 类型 / 提供商 / 模型 / 时间，
支持展开查看细目表 JSON 与校验结论，并可重开落盘的 HTML 文件。
"""

import json
from pathlib import Path

import streamlit as st

from ui.app_state import AppState


def _html_exists(rel_path: str) -> Path | None:
    """检查落盘 HTML 是否存在（历史记录可能指向已删除文件）。"""
    p = Path(rel_path)
    return p if p.exists() else None


def _render_history_card(state, rec):
    """单条历史记录。"""
    title = rec.paper_title or "未命名试卷"
    spec_tag = "✅细目表有效" if rec.spec_valid else "⚠️细目表未通过"
    with st.expander(
        f"{rec.created_at}　|　{title}　|　{rec.paper_type}　|　{rec.provider}",
        expanded=False,
    ):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"**模型**：{rec.model or '-'}")
        with c2:
            st.markdown(f"**题型**：{'、'.join(rec.question_types) or '不限'}")
        with c3:
            st.markdown(f"**校验**：{spec_tag}")
        with c4:
            st.markdown(f"**文件**：{rec.html_path or '-'}")

        if rec.situation:
            st.markdown(f"**情境**：{rec.situation}")

        if rec.spec_json:
            with st.expander("细目表 JSON"):
                try:
                    st.json(json.loads(rec.spec_json))
                except ValueError:
                    st.code(rec.spec_json)

        path = _html_exists(rec.html_path)
        if path:
            c_a, c_b = st.columns(2)
            with c_a:
                if st.button("👁️ 重开预览", key=f"hist_open_{rec.id}"):
                    st.session_state[f"hist_preview_{rec.id}"] = str(path)
            with c_b:
                st.download_button(
                    "📥 下载HTML",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/html",
                    key=f"hist_dl_{rec.id}",
                )
            if st.session_state.get(f"hist_preview_{rec.id}"):
                import streamlit.components.v1 as components

                components.html(path.read_text(encoding="utf-8"), height=700, scrolling=True)
        else:
            st.warning(f"⚠️ 落盘文件不存在：{rec.html_path}（可能已被移动/删除）")


def render(state: AppState):
    """出题历史页渲染入口。"""
    st.title("📜 出题历史")
    st.caption("最近 50 次生成记录；可重开落盘的 HTML 试卷")

    records = state.db.list_history(limit=50)
    if not records:
        st.info("暂无生成记录。去「命题」页生成一份试卷，这里会自动记录。")
        return

    for rec in records:
        _render_history_card(state, rec)
