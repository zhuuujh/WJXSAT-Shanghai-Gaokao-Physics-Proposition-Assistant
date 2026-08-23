# -*- coding: utf-8 -*-
"""knowledge.points 考点库一致性测试。"""

from knowledge.points import VALID_DIFFICULTY, KnowledgeBase


def test_points_count_ge_100(sample_kb):
    assert len(sample_kb.points_list()) >= 100


def test_modules_count(sample_kb):
    assert len(sample_kb.modules) == 6


def test_codes_unique(sample_kb):
    assert sample_kb.validate_raise() >= 0  # 无 error 级问题


def test_validate_no_errors(sample_kb):
    errors = [i for i in sample_kb.validate() if i.severity == "error"]
    assert errors == []


def test_parents_exist(sample_kb):
    for p in sample_kb.points_list():
        assert p.parent in sample_kb._by_code, f"{p.code} parent 缺失"


def test_difficulty_levels_valid(sample_kb):
    for p in sample_kb.points_list():
        assert p.difficulty_level in VALID_DIFFICULTY


def test_required_flags_are_bool(sample_kb):
    for p in sample_kb.points_list():
        assert isinstance(p.is_required, bool)


def test_required_count_reasonable(sample_kb):
    required = sample_kb.required_points()
    assert 60 <= len(required) <= 100


def test_get_returns_point(sample_kb):
    p = sample_kb.get("M1-A-03")
    assert p is not None
    assert p.name == "匀变速直线运动的规律"
    assert p.module == "M1"


def test_get_unknown_returns_none(sample_kb):
    assert sample_kb.get("M1-Z-99") is None


def test_big_point_of(sample_kb):
    p = sample_kb.big_point_of("M1-A-03")
    assert p is not None
    assert p.code == "M1-A"
    assert p.name == "质点的直线运动"


def test_search_name_substring(sample_kb):
    hits = sample_kb.search("匀变速")
    assert any(h.code == "M1-A-03" for h in hits)


def test_search_code_prefix(sample_kb):
    hits = sample_kb.search("M2-A-07")
    assert hits and hits[0].code == "M2-A-07"


def test_module_stats(sample_kb):
    stats = sample_kb.module_stats()
    assert set(stats.keys()) == {"M1", "M2", "M3", "M4", "M5", "M6"}
    assert stats["M1"]["name"] == "力学"
    assert stats["M1"]["point_count"] > 0


def test_children(sample_kb):
    kids = sample_kb.children("M1-A")
    assert len(kids) >= 4
    assert all(k.parent == "M1-A" for k in kids)


def test_module_name_mapping(sample_kb):
    assert sample_kb.module_name("M2") == "电磁学"


# ---------------- 在线编辑 / 持久化 ----------------

def test_update_point_changes_memory_and_raw(sample_kb):
    assert sample_kb.update_point("M1-A-03", name="新名称", is_required=False) is True
    p = sample_kb.get("M1-A-03")
    assert p.name == "新名称"
    assert p.is_required is False
    # 同步回原始 JSON
    raw_item = next(x for x in sample_kb._raw["points"] if x["code"] == "M1-A-03")
    assert raw_item["name"] == "新名称"
    assert raw_item["is_required"] is False


def test_update_point_unknown_code_returns_false(sample_kb):
    assert sample_kb.update_point("M9-Z-99", name="x") is False


def test_to_json_roundtrip(sample_kb):
    text = sample_kb.to_json()
    import json as _json

    data = _json.loads(text)
    assert len(data["points"]) == len(sample_kb.points_list())


def test_save_writes_backup(tmp_path, sample_kb):
    target = tmp_path / "kb.json"
    # 首次写入：无旧文件，无备份
    sample_kb.save(str(target))
    assert target.exists()
    # 二次写入：覆盖前自动备份
    sample_kb.save(str(target))
    assert (tmp_path / "kb.json.bak").exists()
