# -*- coding: utf-8 -*-
"""
============================================
 上海物理等级考智能命题助手（本地版 · 模块化重构）
============================================

入口分发器：只负责页面配置与 sidebar 页面切换。
业务逻辑全部位于 engine/ question_bank/ knowledge/ diagram/ ui/ 包内。

运行方法：
    streamlit run app.py
"""

import streamlit as st

from ui import AppState

# 页面清单（名称 → ui 模块名，模块须暴露 render(state)）。
PAGES = {
    "命题": "pages_prop",
    "题目修改": "pages_revise",
    "题库": "pages_bank",
    "题目校对": "pages_review",
    "考纲对标": "pages_kaogang",
    "出题历史": "pages_history",
    "设置": "pages_settings",
}


def _render(page_name: str, state: AppState):
    """按页面名调用对应 ui.pages_* 的 render(state)。"""
    mod_name = PAGES[page_name]
    module = __import__(f"ui.{mod_name}", fromlist=[mod_name])
    module.render(state)


def main():
    st.set_page_config(
        page_title="上海物理等级考命题助手",
        page_icon="📐",
        layout="wide",
    )

    state = AppState.get()
    page_name = st.sidebar.radio("📂 功能页面", list(PAGES.keys()), index=0, key="nav_page")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔗 外部资源**")
    st.sidebar.link_button("📚 物含妙理 · 物理题库", "https://enjoyphysics.cn/Tiku")
    st.sidebar.link_button("🗄️ EduVault 数字资源库", "https://linkium.mtszedu.com/replix-db/")

    _render(page_name, state)


if __name__ == "__main__":
    main()
