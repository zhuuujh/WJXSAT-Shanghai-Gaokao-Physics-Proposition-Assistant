# -*- coding: utf-8 -*-
"""
knowledge —— 考纲对标包。

内置上海物理等级考考点库（knowledge/data/gaokao_knowledge.json），
并提供加载、查询、一致性校验能力：
- points.py  KnowledgeBase：读取 JSON → 提供 get/search/children/required_points 等
  查询接口与 validate() 一致性校验（code 唯一 / parent 存在 / module 存在等）。

考点库结构：modules（模块）→ big_points（大考点）→ points（子考点）。
子考点编码规范：{模块}-{大考点字母}-{序号}，如 M1-A-01。
"""

__version__ = "1.0.0"
