# -*- coding: utf-8 -*-
"""
pytest 共享 fixtures。

提供：
- tmp_db：临时 SQLite 数据库路径 + QuestionBank 实例
- sample_kb：内置考点库（KnowledgeBase.load_default）
- sample_html_ok / sample_html_bad / sample_html_no_spec：三份细目表测试用 HTML
- fake_uploaded：模拟 streamlit UploadedFile 的简单对象
"""

import io

import pytest


class FakeUploaded:
    """模拟 streamlit UploadedFile 的鸭子类型对象（.name/.type/.getvalue）。"""

    def __init__(self, name, data, media_type=None):
        self.name = name
        self.type = media_type
        self._data = data

    def getvalue(self):
        return self._data


@pytest.fixture
def fake_uploaded():
    def make(name, data=b"", media_type=None):
        return FakeUploaded(name, data, media_type)

    return make


@pytest.fixture
def sample_kb():
    from knowledge.points import KnowledgeBase

    return KnowledgeBase.load_default()


@pytest.fixture
def tmp_db(tmp_path):
    from question_bank.storage import QuestionBank

    db_path = tmp_path / "test_assistant.db"
    db = QuestionBank(str(db_path))
    yield db
    db.close()


# ---------------- 细目表测试用 HTML ----------------

_OK_SPEC_JSON = (
    "#SPEC_TABLE_JSON_START#\n"
    '{"rows":['
    '{"sub":"1-1","point_code":"M1-A-02","point_name":"匀变速直线运动的规律","textbook_source":"必修1 第二章","difficulty":"易","score":4},'
    '{"sub":"1-2","point_code":"M1-A-03","point_name":"v-t图像与x-t图像","textbook_source":"必修1 第二章","difficulty":"中","score":6}'
    '],"score_total":10}\n'
    "#SPEC_TABLE_JSON_END#"
)

_BAD_SPEC_JSON = (
    "#SPEC_TABLE_JSON_START#\n"
    '{"rows":['
    '{"sub":"1-1","point_code":"M1-Z-99","point_name":"不存在考点","textbook_source":"未知","difficulty":"易","score":4},'
    '{"sub":"1-2","point_code":"M1-A-02","point_name":"匀变速直线运动的规律","textbook_source":"必修1 第二章","difficulty":"中","score":6},'
    '{"sub":"1-3","point_code":"M1-A-02","point_name":"重复考点","textbook_source":"必修1 第二章","difficulty":"难","score":8}'
    '],"score_total":18}\n'
    "#SPEC_TABLE_JSON_END#"
)


def _html_with_spec(spec_comment: str) -> str:
    return (
        "<!DOCTYPE html><html><head><title>t</title></head><body>"
        "<h1>试卷</h1>"
        '<table><tr><th>大题</th><th>小题</th><th>考点</th><th>教材来源</th>'
        "<th>难度</th><th>分值</th></tr>"
        '<tr><td>一</td><td>1</td><td>匀变速直线运动的规律</td><td>必修1 第二章</td>'
        "<td>易</td><td>4</td></tr></table>"
        "</body></html>"
        f"<!--{spec_comment}-->"
    )


@pytest.fixture
def sample_html_ok():
    return _html_with_spec(_OK_SPEC_JSON)


@pytest.fixture
def sample_html_bad():
    return _html_with_spec(_BAD_SPEC_JSON)


@pytest.fixture
def sample_html_no_spec():
    return _html_with_spec("")
