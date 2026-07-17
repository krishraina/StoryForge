"""
StoryForge — Review Queue  (Phase 6E, Phase 7 bulk actions)
"""
import streamlit as st
from components.theme    import page_config, apply_theme, COLORS
from components.badges   import status_badge, format_badge
from services.db_service import (
    get_stories_by_status,
    update_story_status,
    get_story,
    bulk_update_story_status,
    bulk_assign_reviewer,
)
from core.constants      import STORY_FORMATS
from core.database       import init_db

init_db()
page_config("Review Queue")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()

c = COLORS

st.markdown(
    f"""
    <div style="margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div class="sf-page-title">📋 Review Queue</div>
        <div class="sf-page-subtitle">Approve or reject stories submitted for publication</div>
    </div>
    """,
    unsafe_allow_html=True,
)

stories = get_stories_by_status("in_review")

if not stories:
    st.markdown(
        f'<div style="text-align:center;padding:4rem;color:{c["text_muted"]};">'
        f'No stories currently in review.<br>'
        f'Generate and submit stories from the <strong>Workspace</strong>.'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    rc1, rc2 = st.columns([3, 2])
    with rc1:
        st.markdown(
            f'<div style="font-size:.82rem;color:{c["text_muted"]};margin-bottom:1.25rem;">'
            f'{len(stories)} story/stories awaiting review'
            f'</div>',
            unsafe_allow_html=True,
        )
    with rc2:
        reviewer_name = st.text_input(
            "Reviewer name",
            value=st.session_state.get("rq_reviewer", "editor"),
            key="rq_reviewer_input",
            placeholder="Your name, for the audit trail",
        )
        st.session_state.rq_reviewer = reviewer_name or "editor"

    selected_ids = []

    for story in stories:
        with st.expander(
            f"{story['participant_name']} — {STORY_FORMATS.get(story['format'], {}).get('label', story['format'])}"
            f"  ·  v{story.get('version', 1)}",
            expanded=False,
        ):
            col_sel, col_meta, col_actions = st.columns([0.3, 2.7, 1])

            with col_sel:
                st.markdown('<div style="padding-top:2rem;"></div>', unsafe_allow_html=True)
                is_selected = st.checkbox(
                    "Select", key=f"rq_sel_{story['id']}", label_visibility="collapsed"
                )
                if is_selected:
                    selected_ids.append(story["id"])

            with col_meta:
                reviewer_chip = (
                    f'<span style="font-size:.72rem;color:{c["text_muted"]};margin-left:auto;">'
                    f'👤 {story["assigned_reviewer"]}</span>'
                    if story.get("assigned_reviewer") else ""
                )
                st.markdown(
                    f"""
                    <div style="display:flex;gap:.75rem;margin-bottom:1rem;align-items:center;">
                        {status_badge('in_review')}
                        {format_badge(story['format'])}
                        <span style="font-size:.75rem;color:{c['text_muted']};">
                            {story.get('program','—')}
                        </span>
                        {reviewer_chip}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="background:{c["surface_alt"]};border:1px solid {c["border"]};'
                    f'border-radius:8px;padding:1rem;font-size:.875rem;'
                    f'color:{c["text_secondary"]};line-height:1.7;white-space:pre-wrap;">'
                    f'{story.get("content","")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if story.get("editor_notes"):
                    st.markdown(
                        f'<div style="font-size:.78rem;color:{c["text_muted"]};'
                        f'margin-top:.65rem;font-style:italic;">'
                        f'Editor notes: {story["editor_notes"]}</div>',
                        unsafe_allow_html=True,
                    )

            with col_actions:
                st.markdown('<div style="padding-top:2rem;"></div>', unsafe_allow_html=True)
                if st.button("✅ Approve", key=f"approve_{story['id']}", use_container_width=True):
                    update_story_status(story["id"], "approved", reviewer=reviewer_name or "editor")
                    st.success("Story approved.")
                    st.rerun()
                if st.button("❌ Reject", key=f"reject_{story['id']}", use_container_width=True):
                    update_story_status(story["id"], "rejected", reviewer=reviewer_name or "editor")
                    st.warning("Story rejected.")
                    st.rerun()
                if st.button("↩ Return to Draft", key=f"draft_{story['id']}", use_container_width=True):
                    update_story_status(story["id"], "draft", reviewer=reviewer_name or "editor")
                    st.info("Returned to draft.")
                    st.rerun()

    # ── Bulk action bar ────────────────────────────────────────────
    st.markdown(
        f'<hr style="border-color:{c["border"]};margin:2rem 0 1.25rem 0;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sf-section-label">Bulk Actions '
        f'<span style="color:{c["text_muted"]};text-transform:none;letter-spacing:0;font-weight:400;">'
        f'— {len(selected_ids)} selected</span></div>',
        unsafe_allow_html=True,
    )

    bc1, bc2, bc3, _gap = st.columns([2, 2, 2, 3])
    bulk_disabled = not selected_ids

    with bc1:
        if st.button(
            "✅ Bulk Approve", use_container_width=True,
            disabled=bulk_disabled, key="rq_bulk_approve",
        ):
            n = bulk_update_story_status(selected_ids, "approved", reviewer=reviewer_name or "editor")
            st.success(f"Approved {n} story/stories.")
            st.rerun()

    with bc2:
        if st.button(
            "❌ Bulk Reject", use_container_width=True,
            disabled=bulk_disabled, key="rq_bulk_reject",
        ):
            n = bulk_update_story_status(selected_ids, "rejected", reviewer=reviewer_name or "editor")
            st.warning(f"Rejected {n} story/stories.")
            st.rerun()

    with bc3:
        if st.button(
            "👤 Assign Reviewer", use_container_width=True,
            disabled=bulk_disabled, key="rq_bulk_assign",
        ):
            n = bulk_assign_reviewer(selected_ids, reviewer_name or "editor")
            st.success(f"Assigned '{reviewer_name or 'editor'}' to {n} story/stories.")
            st.rerun()