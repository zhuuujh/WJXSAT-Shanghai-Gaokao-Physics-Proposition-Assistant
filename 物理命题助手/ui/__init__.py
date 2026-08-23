# -*- coding: utf-8 -*-
"""
ui —— Streamlit 界面层。

本包是唯一依赖 streamlit 的层。每个页面模块暴露 render(state) 函数：
- pages_prop.py      命题页（原 app.py 全部功能迁移 + 缺考点补题 + 细目表校验展示）
- pages_bank.py      题库管理页（CRUD + 检索 + 导入导出）
- pages_kaogang.py   考纲对标页（覆盖统计 + 薄弱考点）
- pages_history.py   出题历史页（列表 + 重开）
- pages_settings.py  设置页

AppState 封装 st.session_state，并懒加载 SQLite 数据库连接。
"""

from .app_state import AppState

__version__ = "2.0.0"

__all__ = ["AppState"]
