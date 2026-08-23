# -*- coding: utf-8 -*-
"""
ui.pages_kaogang —— 考纲对标页。

展示内置上海等级考考点库（141 子考点）的覆盖情况：
- 每个必考点：已收录题目数（point_usage）+ 命中状态（达标/薄弱/未覆盖）
- 薄弱考点（已收录 <2 题）提供「去命题页补题」按钮，跨页预填考点要求
- 模块/大考点两层折叠浏览
"""

import streamlit as st

from ui.app_state import AppState

# 达标阈值：已收录题目数 ≥ 2 视为覆盖充足
_COVERED_THRESHOLD = 2


def _coverage_map(state) -> dict:
    """考点编码 → 已收录题目数。"""
    return state.db.point_usage()


def _render_metrics(state, usage):
    """顶部总览指标。"""
    kb = state.kb
    required = kb.required_points()
    status_rows = kb.coverage_status(usage, _COVERED_THRESHOLD)
    covered_required = sum(1 for r in status_rows if r["status"] == "达标")
    total_questions = state.db.list_questions(page=1, page_size=1)[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("必考点总数", len(required))
    with c2:
        st.metric("覆盖充足", f"{covered_required} / {len(required)}")
    with c3:
        ratio = covered_required / len(required) * 100 if required else 0
        st.metric("达标率", f"{ratio:.0f}%")
    with c4:
        st.metric("题库题目数", total_questions)

    if covered_required < len(required):
        st.info(
            f"还有 **{len(required) - covered_required} 个必考点** 收录题目不足 {_COVERED_THRESHOLD} 道，"
            "可在下方展开模块点击「去命题页补题」。"
        )
    else:
        st.success("🎉 全部必考点均已覆盖！")


def _render_module(state, module_code, usage):
    """单个模块的折叠浏览。"""
    kb = state.kb
    big_points = kb.children(module_code)
    st.markdown(f"#### {kb.module_name(module_code)}（{module_code}）")
    for bp in big_points:
        sub_points = kb.children(bp.code)
        covered = sum(1 for p in sub_points if usage.get(p.code, 0) >= _COVERED_THRESHOLD)
        with st.expander(
            f"{bp.name}　|　覆盖 {covered}/{len(sub_points)}", expanded=False
        ):
            for p in sub_points:
                _render_point_row(state, p, usage)


_COLOR_BY_STATUS = {"达标": "🟢", "未覆盖": "🔴", "薄弱": "🟡"}


def _render_point_row(state, p, usage):
    """单个子考点行。"""
    count = usage.get(p.code, 0)
    required_tag = "必考" if p.is_required else "选考"
    status, tag_color = _classify(p, count)

    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        st.markdown(
            f"{tag_color} **{p.code}**　{p.name}"
            f"<span style='color:#888'>（{required_tag}）</span>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(f"已收录 **{count}** 题　·　{status}")
    with c3:
        if p.is_required and count < _COVERED_THRESHOLD:
            if st.button("去命题页补题", key=f"kaogang_hint_{p.code}"):
                state.set_point_hint([p.code])
                st.success(f"已将考点 {p.code} {p.name} 写入待补清单，请切换到「命题」页生成。")
                st.rerun()


def _classify(p, count):
    """命中状态分类（与 knowledge.coverage_status 同规则，供 UI 取颜色）。"""
    if count >= _COVERED_THRESHOLD:
        return "达标", _COLOR_BY_STATUS["达标"]
    if count > 0:
        return "薄弱", _COLOR_BY_STATUS["薄弱"]
    return "未覆盖", _COLOR_BY_STATUS["未覆盖"]


def _render_mapping_table(state, usage):
    """考纲-题目映射统计表（模块 × 大考点 × 覆盖）。"""
    st.markdown("### 🗺️ 考纲-题目映射总表")
    rows = []
    for m in state.kb.modules:
        for bp in state.kb.children(m["code"]):
            subs = state.kb.children(bp.code)
            q_count = sum(usage.get(p.code, 0) for p in subs)
            req_in_bp = sum(1 for p in subs if p.is_required)
            covered_req = sum(
                1 for p in subs if p.is_required and usage.get(p.code, 0) >= _COVERED_THRESHOLD
            )
            rows.append({
                "模块": state.kb.module_name(m["code"]),
                "大考点": bp.name,
                "子考点数": len(subs),
                "必考点/达标": f"{covered_req}/{req_in_bp}",
                "已收录题数": q_count,
            })
    st.dataframe(rows, hide_index=True,
                 column_config={"已收录题数": st.column_config.NumberColumn(format="%d")})
    total_q = sum(r["已收录题数"] for r in rows)
    st.caption(f"题库按考点关联的题目总数：{total_q}（同一题关联多考点会计入多次）")


def render(state: AppState):
    """考纲对标页渲染入口。"""
    st.title("🎯 考纲对标")
    st.caption("对照内置上海等级考考点库（6模块 / 28大考点 / 141子考点）检查题库覆盖情况")

    # 同步考点镜像到题库表，保证统计可用
    state.sync_kb_to_db()
    usage = _coverage_map(state)
    _render_metrics(state, usage)

    st.markdown("---")
    _render_mapping_table(state, usage)

    st.markdown("---")
    for m in state.kb.modules:
        _render_module(state, m["code"], usage)
