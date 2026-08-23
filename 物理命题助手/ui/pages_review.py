# -*- coding: utf-8 -*-
"""
ui.pages_review —— 题目校对状态机页。

把题库中未定稿的题目逐题人工校对：
- draft（草稿）→ reviewed（已审核）→ approved（已定稿）
- 或直接 approved / rejected（驳回，状态可回退）

配套模型 question_bank.models.ReviewStatus，构成完整校对工作流。
"""

import streamlit as st

from question_bank.models import QuestionFilter, ReviewStatus
from ui.app_state import AppState

_PAGE_SIZE = 10

# 状态 → 展示色/图标
_STATUS_META = {
    ReviewStatus.draft.value: ("草稿", "🟡"),
    ReviewStatus.reviewed.value: ("已审核", "🔵"),
    ReviewStatus.approved.value: ("已定稿", "🟢"),
    ReviewStatus.rejected.value: ("已驳回", "🔴"),
}


def _render_metrics(state):
    """各状态数量指标。"""
    cols = st.columns(len(ReviewStatus.values()))
    for col, s in zip(cols, ReviewStatus.values()):
        total, _ = state.db.list_questions(QuestionFilter(status=s), page=1, page_size=1)
        label, icon = _STATUS_META[s]
        col.metric(f"{icon} {label}", total)


def _point_names(state, codes):
    """考点编码列表 → 可读名称。"""
    names = []
    for code in codes:
        p = state.kb.get(code)
        names.append(f"{code} {p.name if p else ''}".strip())
    return "；".join(names) if names else "未关联考点"


def _render_card(state, q):
    """单题校对卡片。"""
    label, icon = _STATUS_META.get(q.status, (q.status, "⚪"))
    with st.expander(f"#{q.id}　[{label}]　{q.stem[:36]}{'…' if len(q.stem) > 36 else ''}",
                     expanded=False):
        st.markdown(f"**题型**：{q.question_type}　**难度**：{q.difficulty_level}")
        if q.options:
            for i, opt in enumerate(q.options, start=1):
                st.markdown(f"{'ABCDEFGH'[i - 1]}. {opt}")
        st.markdown("**题干**")
        st.write(q.stem)
        st.markdown(f"**答案**：{q.answer or '（无）'}")
        st.markdown(f"**解析**：{q.analysis or '（无）'}")
        if q.source:
            st.markdown(f"**来源**：{q.source}")
        if q.point_codes:
            st.markdown(f"**考点**：{_point_names(state, q.point_codes)}")

        c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
        with c1:
            if st.button("🔵 已审核", key=f"rev_r_{q.id}",
                         disabled=(q.status == ReviewStatus.approved.value)):
                _set_status(state, q.id, ReviewStatus.reviewed.value)
        with c2:
            if st.button("🟢 批准定稿", key=f"rev_a_{q.id}",
                         disabled=(q.status == ReviewStatus.approved.value)):
                _set_status(state, q.id, ReviewStatus.approved.value)
        with c3:
            if st.button("🔴 驳回", key=f"rev_j_{q.id}",
                         disabled=(q.status == ReviewStatus.rejected.value)):
                _set_status(state, q.id, ReviewStatus.rejected.value)
        with c4:
            st.caption(f"收录 {q.created_at[:10]}　|　更新 {q.updated_at[:16]}")


def _set_status(state, qid, new_status):
    """改状态并重跑。"""
    q = state.db.get_question(qid)
    if q is None:
        st.error(f"题目 #{qid} 不存在")
        return
    q.status = new_status
    if state.db.update_question(q):
        st.success(f"题目 #{qid} 状态 → {_STATUS_META[new_status][0]}")
        st.rerun()
    else:
        st.error("更新失败")


def _render_filter():
    """校对状态筛选。"""
    options = ["全部"] + ReviewStatus.values()
    sel = st.selectbox("按状态筛选", options, index=0, key="rev_filter")
    return None if sel == "全部" else sel


def _render_pagination(state, total):
    """简单翻页（相邻页码）。"""
    pages = max(1, -(-total // _PAGE_SIZE))
    page = st.session_state.get("rev_page", 1)
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        if st.button("◀ 上一页", key="rev_prev", disabled=(page <= 1)):
            st.session_state["rev_page"] = max(1, page - 1)
            st.rerun()
    with c2:
        shown = list(range(max(1, page - 2), min(pages, page + 2) + 1))
        cols = st.columns(len(shown))
        for i, col in zip(shown, cols):
            if col.button(f"{i}/{pages}", key=f"rev_pg_{i}", disabled=(i == page)):
                st.session_state["rev_page"] = i
                st.rerun()
    with c3:
        if st.button("下一页 ▶", key="rev_next", disabled=(page >= pages)):
            st.session_state["rev_page"] = min(pages, page + 1)
            st.rerun()


def render(state: AppState):
    """题目校对页渲染入口。"""
    st.title("🔍 题目校对")
    st.caption(
        "逐题校对入库题目：草稿 → 已审核 → 已定稿；可驳回退回。"
        "定稿（approved）的题目才算完成校对闭环。"
    )

    _render_metrics(state)

    status = _render_filter()
    filt = QuestionFilter(status=status)
    page = st.session_state.get("rev_page", 1)

    total, items = state.db.list_questions(filt, page=page, page_size=_PAGE_SIZE)
    st.markdown(f"### 📄 校对队列（{total} 题）")

    if not items:
        st.info("当前筛选下没有题目。去「题库」页收录题目，或切换筛选状态。")
        return

    for q in items:
        _render_card(state, q)

    if total > _PAGE_SIZE:
        _render_pagination(state, total)
