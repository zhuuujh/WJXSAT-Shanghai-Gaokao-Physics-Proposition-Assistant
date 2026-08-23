# -*- coding: utf-8 -*-
"""
question_bank.storage —— SQLite 持久化层。

提供题目 CRUD、题目-考点多对多、检索、出题历史、考点库镜像、统计。
只依赖标准库 sqlite3 / json / dataclasses，可单测。

设计要点：
- 连接使用 check_same_thread=False，兼容 Streamlit 多线程重跑
- 写操作统一用 with self._conn: 事务
- options / tags / question_types / spec_json 等列表或 JSON 字段用
  json.dumps(ensure_ascii=False) 存储
"""

import json
import sqlite3
from pathlib import Path

from .models import ExamRecord, Question, QuestionFilter, ReviewStatus

# 默认数据库路径（应用启动目录下的 data/）
DEFAULT_DB_PATH = str(Path("data") / "physics_assistant.db")

# 建表 SQL（软著 / 教学展示用）
SCHEMA_SQL = """
-- ========== 题目表 ==========
CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_type   TEXT    NOT NULL,
    difficulty_level TEXT   NOT NULL,
    stem            TEXT    NOT NULL,
    options         TEXT,
    answer          TEXT,
    analysis        TEXT,
    source          TEXT,
    source_paper_id INTEGER,
    status          TEXT    NOT NULL DEFAULT 'draft',
    tags            TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ========== 考点表（JSON 考纲库的镜像，供外键/统计） ==========
CREATE TABLE IF NOT EXISTS knowledge_points (
    code             TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    parent_code      TEXT,
    module           TEXT NOT NULL,
    textbook_source  TEXT,
    difficulty_level TEXT,
    is_required      INTEGER NOT NULL DEFAULT 0
);

-- ========== 题目-考点 多对多关联表 ==========
-- 说明：point_code 为软关联（不建外键），因为考点库可能被用户编辑，
-- 题库中的历史考点编码应保持可检索，而不被知识库变更所阻塞。
CREATE TABLE IF NOT EXISTS question_points (
    question_id INTEGER NOT NULL,
    point_code  TEXT    NOT NULL,
    PRIMARY KEY (question_id, point_code),
    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- ========== 出题历史表 ==========
CREATE TABLE IF NOT EXISTS exam_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_title    TEXT,
    paper_type     TEXT NOT NULL,
    provider       TEXT NOT NULL,
    model          TEXT,
    question_types TEXT,
    situation      TEXT,
    html_path      TEXT,
    html_summary   TEXT,
    spec_json      TEXT,
    spec_valid     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_questions_type   ON questions(question_type);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);
CREATE INDEX IF NOT EXISTS idx_question_points_code ON question_points(point_code);
CREATE INDEX IF NOT EXISTS idx_history_created  ON exam_history(created_at);
"""


def _j_dumps(obj):
    """JSON 序列化（保证中文可读）。"""
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def _j_loads(text):
    """JSON 反序列化，空/非法返回空列表。"""
    if not text:
        return []
    try:
        value = json.loads(text)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _row_to_question(row, point_codes=None):
    """数据库行 → Question。"""
    if row is None:
        return None
    return Question(
        id=row[0],
        question_type=row[1],
        difficulty_level=row[2],
        stem=row[3],
        options=_j_loads(row[4]) if row[4] else None,
        answer=row[5] or "",
        analysis=row[6] or "",
        source=row[7] or "",
        source_paper_id=row[8],
        status=row[9],
        tags=_j_loads(row[10]),
        point_codes=point_codes or [],
        created_at=row[11],
        updated_at=row[12],
    )


class QuestionBank:
    """SQLite 题库访问对象。

    示例：
        db = QuestionBank("data/physics_assistant.db")
        db.add_question(Question(stem="…", point_codes=["M1-A-03"]))
        db.list_questions(QuestionFilter(point_code="M1-A-03"))
        db.close()
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # 启用外键约束，保证 question_points 级联删除生效
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self):
        """建表（幂等）。"""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ---------------- 题目 CRUD ----------------

    def add_question(self, q: Question) -> int:
        """新增题目，返回新 id；同时写入题目-考点关联。"""
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO questions (question_type, difficulty_level, stem, options,"
                " answer, analysis, source, source_paper_id, status, tags)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    q.question_type, q.difficulty_level, q.stem,
                    _j_dumps(q.options), q.answer, q.analysis,
                    q.source, q.source_paper_id, q.status, _j_dumps(q.tags),
                ),
            )
            qid = cur.lastrowid
            self._insert_points(qid, q.point_codes)
        return qid

    def update_question(self, q: Question) -> bool:
        """更新题目（需带 id）；关联考点先删后插。返回是否更新到行。"""
        if q.id is None:
            return False
        with self._conn:
            cur = self._conn.execute(
                "UPDATE questions SET question_type=?, difficulty_level=?, stem=?,"
                " options=?, answer=?, analysis=?, source=?, source_paper_id=?,"
                " status=?, tags=?, updated_at=datetime('now','localtime')"
                " WHERE id=?",
                (
                    q.question_type, q.difficulty_level, q.stem,
                    _j_dumps(q.options), q.answer, q.analysis,
                    q.source, q.source_paper_id, q.status, _j_dumps(q.tags),
                    q.id,
                ),
            )
            self._conn.execute("DELETE FROM question_points WHERE question_id=?", (q.id,))
            self._insert_points(q.id, q.point_codes)
        return cur.rowcount > 0

    def delete_question(self, qid: int) -> bool:
        """删除题目（级联删除关联考点）。"""
        with self._conn:
            cur = self._conn.execute("DELETE FROM questions WHERE id=?", (qid,))
        return cur.rowcount > 0

    def get_question(self, qid: int):
        """按 id 取题目（含考点）。"""
        row = self._conn.execute(
            "SELECT * FROM questions WHERE id=?", (qid,)
        ).fetchone()
        if row is None:
            return None
        points = self.get_points_of(qid)
        return _row_to_question(row, points)

    def get_points_of(self, qid: int) -> list:
        """题目关联的考点编码列表。"""
        rows = self._conn.execute(
            "SELECT point_code FROM question_points WHERE question_id=? ORDER BY point_code",
            (qid,),
        ).fetchall()
        return [r["point_code"] for r in rows]

    # ---------------- 检索 ----------------

    def list_questions(self, filt: QuestionFilter | None = None,
                       page: int = 1, page_size: int = 20):
        """按条件检索，返回 (总数, 题目列表)。支持分页。"""
        filt = filt or QuestionFilter()
        where, params = [], []

        if filt.question_type:
            where.append("question_type=?")
            params.append(filt.question_type)
        if filt.difficulty_level:
            where.append("difficulty_level=?")
            params.append(filt.difficulty_level)
        if filt.status:
            where.append("status=?")
            params.append(filt.status)
        if filt.keyword:
            where.append("(stem LIKE ? OR answer LIKE ? OR tags LIKE ?)")
            kw = f"%{filt.keyword}%"
            params += [kw, kw, kw]

        # 按考点过滤：需要关联子查询
        point_filter = None
        if filt.point_code:
            point_filter = filt.point_code

        base = " FROM questions q"
        if point_filter:
            base += " JOIN question_points qp ON qp.question_id = q.id"
            where.append("qp.point_code=?")
            params.append(point_filter)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        total = self._conn.execute(
            f"SELECT COUNT(*) {base}{where_sql}", params
        ).fetchone()[0]

        page = max(1, page)
        offset = (page - 1) * page_size
        rows = self._conn.execute(
            f"SELECT DISTINCT q.* {base}{where_sql}"
            " ORDER BY q.id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

        questions = [_row_to_question(r, self.get_points_of(r["id"])) for r in rows]
        return total, questions

    # ---------------- 出题历史 ----------------

    def record_history(self, rec: ExamRecord) -> int:
        """记录一次出题历史，返回 id。"""
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO exam_history (paper_title, paper_type, provider, model,"
                " question_types, situation, html_path, html_summary, spec_json, spec_valid)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    rec.paper_title, rec.paper_type, rec.provider, rec.model,
                    _j_dumps(rec.question_types), rec.situation, rec.html_path,
                    rec.html_summary, rec.spec_json, int(rec.spec_valid),
                ),
            )
            return cur.lastrowid

    def list_history(self, limit: int = 50) -> list:
        """最近出题历史（倒序）。"""
        rows = self._conn.execute(
            "SELECT * FROM exam_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_history(r) for r in rows]

    def get_history(self, hid: int):
        """按 id 取出题历史。"""
        row = self._conn.execute(
            "SELECT * FROM exam_history WHERE id=?", (hid,)
        ).fetchone()
        return self._row_to_history(row) if row else None

    def _row_to_history(self, row):
        return ExamRecord(
            id=row["id"],
            paper_title=row["paper_title"] or "",
            paper_type=row["paper_type"],
            provider=row["provider"],
            model=row["model"] or "",
            question_types=_j_loads(row["question_types"]),
            situation=row["situation"] or "",
            html_path=row["html_path"] or "",
            html_summary=row["html_summary"] or "",
            spec_json=row["spec_json"] or "",
            spec_valid=bool(row["spec_valid"]),
            created_at=row["created_at"],
        )

    # ---------------- 考点镜像与统计 ----------------

    def import_knowledge(self, kb) -> int:
        """把考点库 JSON 镜像写入 knowledge_points 表（幂等，先清空再写）。"""
        with self._conn:
            self._conn.execute("DELETE FROM knowledge_points")
            rows = []
            for p in kb.points_list():
                rows.append(
                    (p.code, p.name, p.parent, p.module, p.textbook_source,
                     p.difficulty_level, int(p.is_required))
                )
            self._conn.executemany(
                "INSERT INTO knowledge_points (code, name, parent_code, module,"
                " textbook_source, difficulty_level, is_required) VALUES (?,?,?,?,?,?,?)",
                rows,
            )
        return len(rows)

    def point_usage(self) -> dict:
        """考点编码 → 题库中关联题目数。"""
        rows = self._conn.execute(
            "SELECT point_code, COUNT(*) AS c FROM question_points GROUP BY point_code"
        ).fetchall()
        return {r["point_code"]: r["c"] for r in rows}

    def module_stats(self) -> dict:
        """模块 → 统计（题目数、覆盖考点数）。依赖 knowledge_points 镜像。"""
        rows = self._conn.execute(
            "SELECT kp.module,"
            " COUNT(DISTINCT qp.question_id) AS q_count,"
            " COUNT(DISTINCT qp.point_code) AS p_count"
            " FROM question_points qp"
            " JOIN knowledge_points kp ON kp.code = qp.point_code"
            " GROUP BY kp.module"
        ).fetchall()
        return {r["module"]: {"question_count": r["q_count"], "point_count": r["p_count"]}
                for r in rows}

    # ---------------- 内部 ----------------

    def _insert_points(self, qid: int, point_codes: list):
        for code in point_codes or []:
            self._conn.execute(
                "INSERT OR IGNORE INTO question_points (question_id, point_code)"
                " VALUES (?,?)", (qid, code)
            )
