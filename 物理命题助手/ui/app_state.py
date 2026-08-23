# -*- coding: utf-8 -*-
"""
ui.app_state —— 应用全局状态（session_state 封装）。

职责：
- 单例获取 AppState（st.session_state 中缓存）
- 懒加载 SQLite 题库（QuestionBank）与考点库（KnowledgeBase），
  避免每次 rerun 重复建连、重复解析 JSON
- 跨页传参：考纲页标记薄弱考点 → 命题页预填【考点要求】

依赖 streamlit，仅供 ui/ 层使用。
"""

import streamlit as st

from question_bank.storage import DEFAULT_DB_PATH, QuestionBank

# session_state 单例键
_SINGLETON_KEY = "app_state"

# 跨页传递待补考点编码的键
_POINT_HINT_KEY = "point_hint"


class AppState:
    """应用全局状态。用法：state = AppState.get()。"""

    def __init__(self):
        self._db = None
        self._kb = None

    # ---------------- 单例 ----------------

    @classmethod
    def get(cls):
        """获取当前会话的 AppState 单例。"""
        if _SINGLETON_KEY not in st.session_state:
            st.session_state[_SINGLETON_KEY] = cls()
        return st.session_state[_SINGLETON_KEY]

    # ---------------- 懒加载资源 ----------------

    @property
    def db(self) -> QuestionBank:
        """SQLite 题库（按需建连）。"""
        if self._db is None:
            self._db = QuestionBank(DEFAULT_DB_PATH)
        return self._db

    @property
    def kb(self):
        """内置考点库（按需加载一次）。"""
        if self._kb is None:
            from knowledge.points import KnowledgeBase

            self._kb = KnowledgeBase.load_default()
        return self._kb

    def sync_kb_to_db(self) -> int:
        """把考点库镜像写入题库表，返回写入条数（幂等）。"""
        return self.db.import_knowledge(self.kb)

    # ---------------- 跨页传参（考纲 → 命题） ----------------

    @property
    def point_hint(self):
        """待补考点编码列表（None 表示无）。"""
        return st.session_state.get(_POINT_HINT_KEY)

    def set_point_hint(self, codes):
        """标记待补考点，供命题页预填。"""
        st.session_state[_POINT_HINT_KEY] = list(codes or [])

    def clear_point_hint(self):
        """命题页消费完考点要求后清除。"""
        if _POINT_HINT_KEY in st.session_state:
            del st.session_state[_POINT_HINT_KEY]
