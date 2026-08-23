# -*- coding: utf-8 -*-
"""
knowledge.points —— 考点库加载、查询与一致性校验。

考点库以 JSON 形式存放于 knowledge/data/gaokao_knowledge.json（可编辑的真相源），
KnowledgeBase 负责读取并提供查询接口，供题库打标、细目表校验、考纲页统计使用。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

# 合法难度等级（校验用）
VALID_DIFFICULTY = {"基础", "中等", "较难", "综合"}

# 默认考点库文件（相对本文件）
DEFAULT_DATA_FILE = Path(__file__).parent / "data" / "gaokao_knowledge.json"


@dataclass
class KnowledgePoint:
    """单个考点（子考点或大考点）。"""

    code: str
    name: str
    parent: str
    module: str
    textbook_source: str = ""
    difficulty_level: str = "基础"
    is_required: bool = False


@dataclass
class ValidationIssue:
    """考点库一致性校验问题。severity: error / warning。"""

    severity: str
    message: str
    code: str = ""


class KnowledgeBase:
    """加载并查询考点库。

    示例：
        kb = KnowledgeBase.load_default()
        kb.get("M1-A-03")            # → KnowledgePoint 或 None
        kb.required_points()         # → 全部必考子考点
        kb.search("匀变速")          # → 名称/编码模糊匹配
    """

    def __init__(self, data: dict):
        self._raw = data
        self.modules = data.get("modules", [])
        self.big_points = data.get("big_points", [])
        self.points = data.get("points", [])

        # 建立索引：code → KnowledgePoint（模块 + 大考点 + 子考点）
        self._by_code: dict[str, KnowledgePoint] = {}
        for m in self.modules:
            self._by_code[m["code"]] = KnowledgePoint(
                code=m["code"],
                name=m["name"],
                parent="",
                module=m["code"],
                textbook_source=m.get("textbook_source", ""),
                difficulty_level="基础",
                is_required=False,
            )
        for item in self.big_points:
            self._by_code[item["code"]] = KnowledgePoint(**item)
        for item in self.points:
            self._by_code[item["code"]] = KnowledgePoint(**item)

        self._module_by_code = {m["code"]: m for m in self.modules}

    # ---------------- 构造 ----------------

    @classmethod
    def load_default(cls):
        """从内置考点库文件加载。"""
        return cls.from_file(DEFAULT_DATA_FILE)

    @classmethod
    def from_file(cls, path):
        """从指定 JSON 文件加载。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    # ---------------- 查询 ----------------

    def get(self, code):
        """按编码查考点，不存在返回 None。"""
        return self._by_code.get(code)

    def points_list(self):
        """全部子考点（不含大考点）。"""
        return [self.get(p["code"]) for p in self.points]

    def big_points_list(self):
        """全部大考点。"""
        return [self.get(p["code"]) for p in self.big_points]

    def required_points(self):
        """全部必考子考点（is_required=True）。"""
        return [p for p in self.points_list() if p and p.is_required]

    def children(self, code):
        """指定编码（大考点或模块）的直接下级。"""
        return [p for p in self._by_code.values() if p.parent == code]

    def big_point_of(self, code):
        """沿 parent 链向上找大考点；不存在返回 None。"""
        p = self.get(code)
        if not p:
            return None
        if p.parent in self._by_code:
            return self._by_code[p.parent]
        return None

    def module_name(self, module_code):
        """模块编码 → 模块名称。"""
        m = self._module_by_code.get(module_code)
        return m["name"] if m else module_code

    def module_source(self, module_code):
        """模块编码 → 教材来源。"""
        m = self._module_by_code.get(module_code)
        return m.get("textbook_source", "") if m else ""

    def search(self, keyword):
        """按名称/编码模糊匹配（子串，不区分大小写）。"""
        kw = keyword.strip().lower()
        if not kw:
            return []
        result = []
        for p in self._by_code.values():
            if kw in p.name.lower() or kw in p.code.lower():
                result.append(p)
        return result

    # ---------------- 持久化（考点库在线编辑用） ----------------

    def update_point(self, code: str, **fields):
        """更新子考点字段（name / difficulty_level / textbook_source / is_required）。

        同时更新内存对象与原始 JSON 结构（供 save() 持久化）。返回是否命中。
        """
        p = self._by_code.get(code)
        if not p or code not in {item.get("code") for item in self._raw.get("points", [])}:
            return False
        for key, val in fields.items():
            if key == "is_required":
                val = bool(val)
            setattr(p, key, val)
            for item in self._raw["points"]:
                if item.get("code") == code:
                    item[key] = val
        return True

    def to_json(self, pretty: bool = True) -> str:
        """导出当前考点库为 JSON 字符串（中文不转义）。"""
        return json.dumps(self._raw, ensure_ascii=False, indent=2 if pretty else None)

    def save(self, path=None):
        """写回考点库 JSON 文件（默认源文件）。写前自动备份为 <path>.bak。

        建议先 validate_raise() 确保数据合法再保存。返回写入路径。
        """
        target = Path(path) if path else DEFAULT_DATA_FILE
        if target.exists():
            backup = str(target) + ".bak"
            try:
                import shutil

                shutil.copy(target, backup)
            except OSError:
                pass
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return str(target)

    def coverage_status(self, usage: dict, threshold: int = 2):
        """按 usage（考点编码→已收录题目数）计算每个必考点命中状态。

        返回 [{point, count, status}]，status ∈ 未覆盖 / 薄弱 / 达标：
        - 未覆盖：count == 0
        - 薄弱：  0 < count < threshold
        - 达标：  count >= threshold
        """
        rows = []
        for p in self.required_points():
            n = usage.get(p.code, 0)
            status = "达标" if n >= threshold else ("薄弱" if n > 0 else "未覆盖")
            rows.append({"point": p, "count": n, "status": status})
        return rows

    def module_stats(self):
        """返回 {module_code: {"name":…, "big_count":…, "point_count":…, "required_count":…}}。"""
        stats = {}
        for m in self.modules:
            bigs = [b for b in self.big_points if b["module"] == m["code"]]
            pts = [p for p in self.points if p["module"] == m["code"]]
            req = [p for p in pts if p.get("is_required")]
            stats[m["code"]] = {
                "name": m["name"],
                "textbook_source": m.get("textbook_source", ""),
                "big_count": len(bigs),
                "point_count": len(pts),
                "required_count": len(req),
            }
        return stats

    # ---------------- 一致性校验 ----------------

    def validate(self):
        """校验考点库一致性，返回 ValidationIssue 列表。

        校验项：① 全库 code 唯一；② 大考点/子考点的 parent 存在；
        ③ module 字段存在于 modules；④ difficulty_level 合法；⑤ is_required 为布尔。
        """
        issues = []

        seen_codes = set()
        for p in self._by_code.values():
            if p.code in seen_codes:
                issues.append(ValidationIssue("error", f"编码重复: {p.code}", p.code))
            seen_codes.add(p.code)

        for p in self._by_code.values():
            if p.parent and p.parent not in self._by_code:
                issues.append(ValidationIssue(
                    "error", f"{p.code} 的 parent 不存在: {p.parent}", p.code))
            if p.module not in self._module_by_code:
                issues.append(ValidationIssue(
                    "error", f"{p.code} 的 module 不存在: {p.module}", p.code))
            if p.difficulty_level not in VALID_DIFFICULTY:
                issues.append(ValidationIssue(
                    "warning", f"{p.code} 难度等级非法: {p.difficulty_level}", p.code))
            if not isinstance(p.is_required, bool):
                issues.append(ValidationIssue(
                    "warning", f"{p.code} 的 is_required 非布尔", p.code))

        return issues

    def validate_raise(self):
        """校验并抛异常（error 级问题），返回校验通过数。"""
        issues = self.validate()
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            msgs = "; ".join(i.message for i in errors)
            raise ValueError(f"考点库一致性校验失败: {msgs}")
        return len(issues)
