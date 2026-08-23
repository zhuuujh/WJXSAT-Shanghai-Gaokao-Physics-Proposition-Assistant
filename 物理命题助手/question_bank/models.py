# -*- coding: utf-8 -*-
"""
question_bank.models —— 题目与出题历史数据模型。

使用 dataclass + Enum 定义结构化数据，便于类型检查、序列化与测试。
"""

from dataclasses import dataclass, field
from enum import Enum


class QuestionType(str, Enum):
    """题型。"""

    单选 = "单选"
    多选 = "多选"
    填空 = "填空"
    计算 = "计算"
    论证简答 = "论证/简答"
    作图 = "作图"

    @classmethod
    def values(cls):
        return [t.value for t in cls]


class DifficultyLevel(str, Enum):
    """难度等级。"""

    基础 = "基础"
    中等 = "中等"
    较难 = "较难"
    综合 = "综合"

    @classmethod
    def values(cls):
        return [d.value for d in cls]


class ReviewStatus(str, Enum):
    """题目校对状态机。"""

    draft = "draft"                # 草稿
    reviewed = "reviewed"          # 已审核
    approved = "approved"          # 已定稿
    rejected = "rejected"          # 已驳回

    @classmethod
    def values(cls):
        return [s.value for s in cls]


@dataclass
class Question:
    """一道题目。point_codes 与 tags 为列表（JSON 序列化存储）。"""

    id: int | None = None
    question_type: str = QuestionType.计算.value
    difficulty_level: str = DifficultyLevel.中等.value
    stem: str = ""
    options: list[str] | None = None       # 选择题选项；非选择题为 None
    answer: str = ""
    analysis: str = ""
    source: str = ""                       # 真题 / 自编 / 教材改编 / 用户上传
    source_paper_id: int | None = None     # 来源试卷（exam_history.id）
    status: str = ReviewStatus.draft.value
    tags: list[str] = field(default_factory=list)
    point_codes: list[str] = field(default_factory=list)   # 考点编码（多对多）
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ExamRecord:
    """一次出题历史记录。spec_json 为细目表 JSON 原文本（未解析时为空串）。"""

    id: int | None = None
    paper_title: str = ""
    paper_type: str = "完整试卷"           # 1道大题 / 完整试卷 / 补充题
    provider: str = "claude"
    model: str = ""
    question_types: list[str] = field(default_factory=list)
    situation: str = ""
    html_path: str = ""                    # 生成的 试卷_*.html 相对路径
    html_summary: str = ""                 # 摘要（HTML 长度或开头片段）
    spec_json: str = ""
    spec_valid: bool = False
    created_at: str = ""


@dataclass
class QuestionFilter:
    """题库检索条件（全部可空，None 表示不过滤）。"""

    question_type: str | None = None
    difficulty_level: str | None = None
    status: str | None = None
    point_code: str | None = None
    keyword: str | None = None
