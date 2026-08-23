# -*- coding: utf-8 -*-
"""question_bank 存储层测试（临时 SQLite，不触网）。"""

import pytest

from question_bank.io_utils import (
    export_all,
    import_json,
    questions_from_json,
    questions_to_json,
)
from question_bank.models import ExamRecord, Question, QuestionFilter
from question_bank.storage import QuestionBank


def _sample_question(point_codes=None, question_type="计算", difficulty="中等", stem="题干A"):
    return Question(
        question_type=question_type,
        difficulty_level=difficulty,
        stem=stem,
        options=["a", "b", "c"] if question_type in ("单选", "多选") else None,
        answer="答案",
        analysis="解析",
        source="真题",
        tags=["力学"],
        point_codes=point_codes or ["M1-A-03"],
    )


# ---------------- add / get / update / delete ----------------

def test_add_get_question(tmp_db):
    qid = tmp_db.add_question(_sample_question())
    got = tmp_db.get_question(qid)
    assert got.id == qid
    assert got.stem == "题干A"
    assert got.question_type == "计算"
    assert got.tags == ["力学"]
    assert got.created_at  # 时间戳自动生成


def test_add_points_m2m(tmp_db):
    qid = tmp_db.add_question(_sample_question(point_codes=["M1-A-03", "M1-A-05"]))
    points = tmp_db.get_points_of(qid)
    assert set(points) == {"M1-A-03", "M1-A-05"}


def test_update_question_replaces_points(tmp_db):
    qid = tmp_db.add_question(_sample_question(point_codes=["M1-A-03"]))
    q = tmp_db.get_question(qid)
    q.stem = "新题干"
    q.point_codes = ["M2-B-05"]
    assert tmp_db.update_question(q) is True
    got = tmp_db.get_question(qid)
    assert got.stem == "新题干"
    assert got.point_codes == ["M2-B-05"]


def test_delete_cascades_points(tmp_db):
    qid = tmp_db.add_question(_sample_question(point_codes=["M1-A-03"]))
    assert tmp_db.delete_question(qid) is True
    assert tmp_db.get_question(qid) is None
    assert tmp_db.get_points_of(qid) == []


def test_update_missing_id_returns_false(tmp_db):
    assert tmp_db.update_question(Question(id=999, stem="x")) is False


# ---------------- 检索 ----------------

def test_list_questions_filters(tmp_db):
    tmp_db.add_question(_sample_question(stem="A", question_type="计算"))
    tmp_db.add_question(_sample_question(stem="B", question_type="多选", difficulty="较难",
                                         point_codes=["M2-A-07"]))
    total, items = tmp_db.list_questions(QuestionFilter(question_type="计算"))
    assert total == 1 and items[0].stem == "A"

    total, items = tmp_db.list_questions(QuestionFilter(difficulty_level="较难"))
    assert total == 1 and items[0].stem == "B"

    total, items = tmp_db.list_questions(QuestionFilter(point_code="M2-A-07"))
    assert total == 1 and items[0].stem == "B"


def test_keyword_search(tmp_db):
    tmp_db.add_question(_sample_question(stem="带电粒子在磁场中运动"))
    total, items = tmp_db.list_questions(QuestionFilter(keyword="磁场"))
    assert total == 1
    assert "磁场" in items[0].stem


def test_pagination(tmp_db):
    for i in range(5):
        tmp_db.add_question(_sample_question(stem=f"题{i}"))
    total, page1 = tmp_db.list_questions(page=1, page_size=3)
    _, page2 = tmp_db.list_questions(page=2, page_size=3)
    assert total == 5
    assert len(page1) == 3 and len(page2) == 2
    # 倒序：page1 是 id 5,4,3
    assert page1[0].stem == "题4"


# ---------------- 出题历史 ----------------

def test_record_and_list_history(tmp_db):
    rid = tmp_db.record_history(ExamRecord(
        paper_title="极光大题", paper_type="完整试卷", provider="claude",
        model="claude-sonnet-5", question_types=["多选", "计算"],
        situation="极光", html_path="试卷_123.html", html_summary="len=1000",
        spec_json='{"rows":[]}', spec_valid=True,
    ))
    recs = tmp_db.list_history()
    assert len(recs) == 1
    got = tmp_db.get_history(rid)
    assert got.paper_title == "极光大题"
    assert got.question_types == ["多选", "计算"]
    assert got.spec_valid is True


# ---------------- JSON 导入导出 ----------------

def test_json_roundtrip(tmp_db):
    tmp_db.add_question(_sample_question(stem="A", point_codes=["M1-A-03"]))
    tmp_db.add_question(_sample_question(stem="B", point_codes=["M2-B-05"]))
    text = export_all(tmp_db)
    parsed = questions_from_json(text)
    assert len(parsed) == 2
    assert parsed[0].point_codes

    # 导入到新库
    db2 = QuestionBank(str(tmp_db.db_path) + ".2")
    try:
        report = import_json(db2, text)
        assert report.total == 2 and report.imported == 2 and report.errors == []
        total, items = db2.list_questions()
        assert total == 2
    finally:
        db2.close()


def test_import_invalid_json_reports_error(tmp_db):
    report = import_json(tmp_db, "not json{{{")
    assert report.total == 0 and report.failed == 0


def test_export_import_empty(tmp_db):
    text = export_all(tmp_db)
    assert json_loads(text) == []


def json_loads(text):
    import json
    return json.loads(text)


# ---------------- 考点镜像与统计 ----------------

def test_import_knowledge_and_stats(tmp_db, sample_kb):
    n = tmp_db.import_knowledge(sample_kb)
    assert n == len(sample_kb.points_list()) > 100

    qid = tmp_db.add_question(_sample_question(point_codes=["M1-A-03", "M1-A-05"]))
    usage = tmp_db.point_usage()
    assert usage.get("M1-A-03") == 1

    stats = tmp_db.module_stats()
    assert stats["M1"]["question_count"] == 1
    assert stats["M1"]["point_count"] == 2
