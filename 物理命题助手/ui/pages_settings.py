# -*- coding: utf-8 -*-
"""
ui.pages_settings —— 设置页。

信息类：版本、考点库规模、数据库路径与统计、命题规范只读预览。
操作类：同步考点库到题库、清空题库（危险操作，需输入确认词）。
"""

import streamlit as st

from engine import prompts as prompts_mod
from ui.app_state import AppState


def _render_about():
    """版本与考点库概况。"""
    st.markdown("### ℹ️ 关于")
    kb = AppState.get().kb
    st.markdown(
        f"- **版本**：{prompts_mod.PROMPT_VERSION}（命题规范版本）　·　"
        f"UI {__import__('ui').__version__}"
    )
    st.markdown(
        f"- **考点库**：{len(kb.modules)} 模块 / {len(kb.big_points_list())} 大考点 / "
        f"{len(kb.points_list())} 子考点（其中必考 {len(kb.required_points())} 个）"
    )
    st.markdown(
        "- **结构**：`engine/`（命题引擎，不含 streamlit）→ `question_bank/`（SQLite 题库）→ "
        "`knowledge/`（考纲考点库）→ `ui/`（界面层）"
    )


def _render_db(state):
    """数据库统计与维护操作。"""
    st.markdown("### 🗄️ 题库数据")
    total, _ = state.db.list_questions(page=1, page_size=1)
    histories = len(state.db.list_history(limit=100000))
    st.markdown(f"- **数据库**：`{state.db.db_path}`")
    st.markdown(f"- **题目数**：{total}　|　**出题历史**：{histories} 条")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 重新同步考点库镜像", key="set_sync"):
            n = state.sync_kb_to_db()
            st.success(f"已同步 {n} 个考点到数据库镜像表（幂等）。")
    with c2:
        st.caption("题库 JSON 备份请前往「题库」页导出。")


def _render_prompt_preview():
    """命题规范只读预览。"""
    st.markdown("### 📜 命题规范（只读预览）")
    st.caption(
        "命题规范是系统提示词的核心资产，唯一真源在 `engine/prompts.py`。"
        "修改请直接编辑该文件（注意保持 6 个规则块标题完整，启动时会自检）。"
    )
    with st.expander("查看完整命题规范（只读）"):
        st.code(prompts_mod.命题规范, language="text")


def _render_kb_editor(state):
    """考点库在线编辑：选中考点 → 修改 → 校验 → 备份写回 JSON。"""
    st.markdown("### 🧩 考点库编辑（可编辑 JSON 的 UI 入口）")
    st.caption(
        "修改会先备份为 `gaokao_knowledge.json.bak` 再写回源文件；"
        "保存前自动做一致性校验（编码唯一 / parent 存在 / 难度合法）。"
    )
    kb = state.kb

    c1, c2 = st.columns([1, 2])
    with c1:
        # 模块 → 大考点 → 子考点 三级选择
        module_codes = [m["code"] for m in kb.modules]
        module = st.selectbox("模块", module_codes,
                              format_func=lambda c: kb.module_name(c), key="kbe_mod")
        bigs = kb.children(module)
        if not bigs:
            st.info("该模块暂无大考点")
            return
        big_label = st.selectbox(
            "大考点", [b.code for b in bigs],
            format_func=lambda c: f"{c} {kb.get(c).name}", key="kbe_big")
        subs = kb.children(big_label)
        if not subs:
            st.info("该大考点暂无子考点")
            return
        point = st.selectbox(
            "子考点", [p.code for p in subs],
            format_func=lambda c: f"{c} {kb.get(c).name}", key="kbe_point")
        p = kb.get(point)
        if p is None:
            return

    with c2:
        st.markdown(f"**当前**：`{p.code}`　{p.name}")
        with st.form("kb_edit_form"):
            name = st.text_input("考点名称", value=p.name)
            diff = st.selectbox(
                "难度等级", ["基础", "中等", "较难", "综合"],
                index=["基础", "中等", "较难", "综合"].index(p.difficulty_level)
                if p.difficulty_level in ("基础", "中等", "较难", "综合") else 1,
                key="kbe_diff",
            )
            source = st.text_input("教材来源", value=p.textbook_source)
            is_required = st.checkbox("必考点", value=p.is_required)
            submitted = st.form_submit_button("💾 保存修改")
            if submitted:
                ok = kb.update_point(
                    p.code, name=name, difficulty_level=diff,
                    textbook_source=source, is_required=is_required,
                )
                if not ok:
                    st.error("保存失败：考点编码不存在")
                else:
                    try:
                        kb.validate_raise()
                        saved = kb.save()
                        st.success(f"✅ 已保存到 `{saved}`（备份为 .bak）")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"❌ 校验未通过，已拒绝写回：{e}")
                        # 回滚内存修改：重新加载
                        st.rerun()


def _render_danger(state):
    """危险操作：清空题库。"""
    st.markdown("### ⚠️ 危险操作")
    confirm = st.text_input(
        "输入「清空题库」后点击下方按钮（会删除全部题目与历史，不可恢复）",
        key="set_confirm",
    )
    if st.button("🗑️ 清空题库", disabled=(confirm != "清空题库"),
                 key="set_clear", type="secondary"):
        # 直接删除全部题目（级联清空关联考点）
        total, items = state.db.list_questions(page=1, page_size=100000)
        for q in items:
            state.db.delete_question(q.id)
        st.warning(f"已清空 {total} 道题目。历史记录保留，如要删除请删除数据库文件 `{state.db.db_path}`。")
        st.rerun()


def render(state: AppState):
    """设置页渲染入口。"""
    st.title("⚙️ 设置")
    st.caption("关于本工具、题库数据维护、命题规范预览")

    _render_about()
    st.markdown("---")
    _render_db(state)
    st.markdown("---")
    _render_kb_editor(state)
    st.markdown("---")
    _render_prompt_preview()
    st.markdown("---")
    _render_danger(state)
