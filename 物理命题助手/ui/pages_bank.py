# -*- coding: utf-8 -*-
"""
ui.pages_bank —— 题库管理页。

功能：
- 检索：按题型 / 难度 / 状态 / 考点 / 关键词过滤，分页浏览
- 新增 / 编辑 / 删除题目（编辑用 session_state 记录目标 id）
- 题目-考点多对多关联（multiselect 从考点库选取）
- JSON 导出（下载）/ 导入（上传），用于软著备份与跨机迁移
"""

import streamlit as st

from question_bank.io_utils import export_all, import_json
from question_bank.models import (
    DifficultyLevel,
    Question,
    QuestionFilter,
    QuestionType,
    ReviewStatus,
)
from ui.app_state import AppState

_EDIT_KEY = "bank_editing_id"
_PAGE_KEY = "bank_page"
_PAGE_SIZE = 8


def _filter_bar(state) -> QuestionFilter:
    """检索条件栏。"""
    st.markdown("### 🔍 检索")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        qtype = st.selectbox("题型", ["全部"] + QuestionType.values())
    with c2:
        diff = st.selectbox("难度", ["全部"] + DifficultyLevel.values())
    with c3:
        status = st.selectbox("状态", ["全部"] + ReviewStatus.values())
    with c4:
        keyword = st.text_input("关键词（题干/答案/标签）", placeholder="如：磁场")

    # 考点筛选：从考点库生成下拉（含 "全部"）
    all_points = ["全部"] + [f"{p.code} {p.name}" for p in state.kb.points_list()]
    point_label = st.selectbox("考点", all_points, key="bank_point_filter")
    point_code = "" if point_label == "全部" else point_label.split(" ")[0]

    return QuestionFilter(
        question_type=None if qtype == "全部" else qtype,
        difficulty_level=None if diff == "全部" else diff,
        status=None if status == "全部" else status,
        point_code=point_code or None,
        keyword=keyword.strip() or None,
    )


def _render_question_card(state, q: Question):
    """单题卡片（题干/选项/解析/考点 + 编辑/删除按钮）。"""
    with st.expander(f"#{q.id}　{q.stem[:40]}{'…' if len(q.stem) > 40 else ''}", expanded=False):
        st.markdown(f"**题型**：{q.question_type}　**难度**：{q.difficulty_level}　**状态**：{q.status}")
        if q.options:
            for i, opt in enumerate(q.options, start=1):
                st.markdown(f"{'ABCDEFGH'[i-1]}. {opt}")
        st.markdown("**题干**")
        st.write(q.stem)
        if q.answer:
            st.markdown(f"**答案**：{q.answer}")
        if q.analysis:
            st.markdown(f"**解析**：{q.analysis}")
        if q.source:
            st.markdown(f"**来源**：{q.source}")
        if q.tags:
            st.markdown(f"**标签**：{'、'.join(q.tags)}")
        if q.point_codes:
            names = []
            for code in q.point_codes:
                p = state.kb.get(code)
                names.append(f"{code} {p.name if p else ''}".strip())
            st.markdown("**考点**：" + "；".join(names))

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✏️ 编辑", key=f"edit_{q.id}"):
                st.session_state[_EDIT_KEY] = q.id
                st.rerun()
        with c2:
            if st.button("🗑️ 删除", key=f"del_{q.id}"):
                state.db.delete_question(q.id)
                st.success(f"已删除题目 #{q.id}")
                st.rerun()
        with c3:
            st.caption(f"收录于 {q.created_at[:10]}")


def _point_options(state):
    """考点库 → (label→code) 映射，供新增/编辑时多选。"""
    return {
        f"{p.code} {p.name}": p.code for p in state.kb.points_list()
    }


def _question_form(state, q: Question | None, form_key: str):
    """新增 / 编辑共用的表单。返回是否提交成功。"""
    with st.form(form_key):
        c1, c2, c3 = st.columns(3)
        with c1:
            qtype = st.selectbox("题型", QuestionType.values(),
                                 index=QuestionType.values().index(q.question_type)
                                 if q.question_type in QuestionType.values() else 0)
        with c2:
            diff = st.selectbox("难度", DifficultyLevel.values(),
                                index=DifficultyLevel.values().index(q.difficulty_level)
                                if q.difficulty_level in DifficultyLevel.values() else 1)
        with c3:
            status = st.selectbox("状态", ReviewStatus.values(),
                                  index=ReviewStatus.values().index(q.status)
                                  if q.status in ReviewStatus.values() else 0)

        stem = st.text_area("题干", value=q.stem, height=110, placeholder="输入题目内容……")
        options = st.text_area(
            "选择题选项（每行一个，非选择题留空）",
            value="\n".join(q.options) if q.options else "",
            height=90,
        )
        c4, c5 = st.columns(2)
        with c4:
            answer = st.text_area("答案", value=q.answer, height=60)
        with c5:
            analysis = st.text_area("解析", value=q.analysis, height=60)

        c6, c7, c8 = st.columns(3)
        with c6:
            source = st.text_input("来源", value=q.source, placeholder="真题 / 自编 / 教材改编")
        with c7:
            tags = st.text_input("标签（逗号分隔）", value="、".join(q.tags) or ", ".join(q.tags),
                                 placeholder="如：力学, 情境题")
        with c8:
            point_labels = st.multiselect(
                "关联考点（多选）",
                list(_point_options(state).keys()),
                default=[f"{c} {state.kb.get(c).name}" for c in q.point_codes
                         if state.kb.get(c)],
            )

        submitted = st.form_submit_button("💾 保存题目")
        if submitted:
            opts = [o.strip() for o in options.splitlines() if o.strip()] or None
            q.question_type = qtype
            q.difficulty_level = diff
            q.status = status
            q.stem = stem
            q.options = opts
            q.answer = answer
            q.analysis = analysis
            q.source = source
            q.tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
            q.point_codes = [_point_options(state)[k] for k in point_labels]
            return True
    return False


def _render_add(state):
    """新增题目表单。"""
    st.markdown("### ➕ 新增题目")
    q = Question()
    if _question_form(state, q, "form_add"):
        qid = state.db.add_question(q)
        st.success(f"已新增题目 #{qid}")
        st.rerun()


def _render_edit(state):
    """编辑中的题目（session_state 记录 id）。"""
    editing_id = st.session_state.get(_EDIT_KEY)
    if not editing_id:
        return
    q = state.db.get_question(editing_id)
    if q is None:
        del st.session_state[_EDIT_KEY]
        return
    st.markdown(f"### ✏️ 编辑题目 #{editing_id}")
    if _question_form(state, q, "form_edit"):
        if state.db.update_question(q):
            st.success(f"已更新题目 #{editing_id}")
        del st.session_state[_EDIT_KEY]
        st.rerun()
    if st.button("取消编辑", key="bank_cancel_edit"):
        del st.session_state[_EDIT_KEY]
        st.rerun()


def _render_io(state):
    """JSON 导出 / 导入。"""
    st.markdown("### 💾 导入导出")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("导出当前全部题目为 JSON（可备份 / 跨机迁移）")
        text = export_all(state.db)
        st.download_button(
            "📤 导出 questions.json",
            data=text.encode("utf-8"),
            file_name="questions.json",
            mime="application/json",
            key="bank_export_dl",
        )
    with c2:
        uploaded = st.file_uploader("导入 JSON 覆盖式追加", type=["json"],
                                    key="bank_import_upload")
        if uploaded and st.button("📥 开始导入", key="bank_import_btn"):
            text = uploaded.getvalue().decode("utf-8")
            report = import_json(state.db, text)
            st.success(f"导入完成：共 {report.total} 条，成功 {report.imported}，失败 {report.failed}")
            if report.errors:
                with st.expander("失败明细"):
                    for e in report.errors[:20]:
                        st.code(e)
            st.rerun()

    # 模块统计
    stats = state.db.module_stats()
    if stats:
        with st.expander("📊 模块-题目统计"):
            for mod in sorted(stats):
                st.markdown(
                    f"- **{state.kb.module_name(mod)}**：{stats[mod]['question_count']} 题，"
                    f"覆盖 {stats[mod]['point_count']} 个考点"
                )


def render(state: AppState):
    """题库页渲染入口。"""
    st.title("🗃️ 题库管理")
    st.caption("收录/检索/校对题目；题目与考纲考点多对多关联，供考纲对标统计")

    # 先渲染编辑区（置顶，便于定位）
    _render_edit(state)

    filt = _filter_bar(state)
    page = st.session_state.get(_PAGE_KEY, 1)

    total, items = state.db.list_questions(filt, page=page, page_size=_PAGE_SIZE)
    st.markdown(f"### 📄 题目列表（共 {total} 题）")

    for q in items:
        _render_question_card(state, q)

    # 分页（编号封顶，避免页数过多时横排过宽）
    if total > _PAGE_SIZE:
        pages = max(1, -(-total // _PAGE_SIZE))
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1:
            if st.button("◀ 上一页", key="bank_prev", disabled=(page <= 1)):
                st.session_state[_PAGE_KEY] = max(1, page - 1)
                st.rerun()
        with c2:
            shown = list(range(max(1, page - 3), min(pages, page + 3) + 1))
            cols = st.columns(len(shown))
            for i, col in zip(shown, cols):
                if col.button(f"{i}/{pages}", key=f"bank_pg_{i}", disabled=(i == page)):
                    st.session_state[_PAGE_KEY] = i
                    st.rerun()
        with c3:
            if st.button("下一页 ▶", key="bank_next", disabled=(page >= pages)):
                st.session_state[_PAGE_KEY] = min(pages, page + 1)
                st.rerun()

    st.markdown("---")
    _render_add(state)
    st.markdown("---")
    _render_io(state)
