# -*- coding: utf-8 -*-
"""
question_bank.io_utils —— 题库 JSON 导入导出。

用于软著备份、题库迁移、跨机交换。JSON 使用 ensure_ascii=False，人类可读。
"""

import json
from dataclasses import asdict

from .models import Question


class ImportReport:
    """导入结果汇总。"""

    def __init__(self, total=0, imported=0, errors=None):
        self.total = total
        self.imported = imported
        self.errors = errors or []

    @property
    def failed(self):
        return self.total - self.imported


def questions_to_json(items, pretty=True):
    """题目列表 → JSON 字符串（不含 point_codes 以外的内部字段冗余）。"""
    records = []
    for q in items:
        d = asdict(q)
        # 去掉数据库生成字段，保持交换格式干净
        d.pop("id", None)
        d.pop("created_at", None)
        d.pop("updated_at", None)
        records.append(d)
    return json.dumps(records, ensure_ascii=False, indent=2 if pretty else None)


def questions_from_json(text):
    """JSON 字符串 → 题目列表。非法行被跳过。"""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            q = Question(
                question_type=item.get("question_type", "计算"),
                difficulty_level=item.get("difficulty_level", "中等"),
                stem=item.get("stem", ""),
                options=item.get("options"),
                answer=item.get("answer", ""),
                analysis=item.get("analysis", ""),
                source=item.get("source", ""),
                status=item.get("status", "draft"),
                tags=item.get("tags") or [],
                point_codes=item.get("point_codes") or [],
            )
            questions.append(q)
        except (TypeError, ValueError):
            continue
    return questions


def export_all(db, path=None):
    """导出题库全部题目为 JSON 字符串；path 非空时写盘并返回。"""
    total, items = db.list_questions(page=1, page_size=100000)
    text = questions_to_json(items)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def import_json(db, text):
    """导入 JSON 到题库，逐题容错（单题失败不中断）。返回 ImportReport。"""
    questions = questions_from_json(text)
    report = ImportReport(total=len(questions))
    for q in questions:
        try:
            db.add_question(q)
            report.imported += 1
        except Exception as e:  # noqa: BLE001 —— 单题失败仅记录
            report.errors.append(f"{getattr(q, 'stem', '')[:30]}...: {e}")
    return report
