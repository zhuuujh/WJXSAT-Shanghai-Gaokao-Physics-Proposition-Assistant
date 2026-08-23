# -*- coding: utf-8 -*-
"""
question_bank —— 题库管理包。

基于 SQLite 的题目持久化、检索、JSON 导入导出，以及出题历史记录。
- models.py   题目 / 出题历史 / 筛选条件数据模型（dataclass + Enum）
- storage.py  SQLite CRUD、题目-考点多对多、检索、历史
- io_utils.py JSON 导入导出（软著/备份/迁移）

依赖方向：本包不依赖 streamlit，仅依赖标准库 sqlite3 / json / dataclasses。
"""

__version__ = "1.0.0"
