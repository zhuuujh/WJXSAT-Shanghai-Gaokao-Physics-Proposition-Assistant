# -*- coding: utf-8 -*-
"""
engine —— 命题引擎包。

本包与 streamlit 完全解耦，全部为纯 Python 逻辑，可独立单测、可复用。
包含：
- prompts.py   命题规范唯一来源（6 个规则块 + 双向细目表 JSON 规则）
- builder.py   文件解析 / 文本截断 / user_text 组装 / HTML 清理（纯函数）
- provider.py  Claude / DeepSeek 双提供商适配层
- validator.py 双向细目表 JSON 提取 / 校验 / 覆盖分析

依赖方向：ui 依赖 engine；engine 不依赖 ui。
"""

__version__ = "1.0.0"
