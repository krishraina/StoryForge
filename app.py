"""
StoryForge — Dashboard Home  (Phase 6H polish)
"""
import streamlit as st
from components.theme    import page_config, apply_theme, COLORS
from components.sidebar  import render_sidebar
from services.db_service import get_dashboard_stats, get_all_stories
from core.database       import init_db
from core.config         import APP_NAME, APP_TAGLINE, ORG_NAME
from core.constants      import STORY_FORMATS

# ── Bootstrap ─────────────────────────────────────────────────────────
init_db()
page_config("Dashboard")
apply_theme()
render_sidebar()

c = COLORS

# ── Live data ─────────────────────────────────────────────────────────
stats          = get_dashboard_stats()
recent_stories = get_all_stories()[:6]   # 6 most recent for the feed


# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="margin-bottom:2.5rem;padding-bottom:1.5rem;
         border-bottom:1px solid {c['border']};">
        <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.4rem;">
            <span style="font-size:1.5rem;">&#10022;</span>
            <span style="font-size:1.5rem;font-weight:800;
                  color:{c['text_primary']};letter-spacing:-.03em;">
                {APP_NAME}
            </span>
        </div>
        <div style="font-size:.875rem;color:{c['text_muted']};">
            {APP_TAGLINE}&nbsp;&nbsp;&#183;&nbsp;&nbsp;{ORG_NAME}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════
# STATS ROW  — themed HTML cards (replaces st.metric())
# ══════════════════════════════════════════════════════════════════════

# The Dashboard answers "what needs my attention right now" — so the
# strip has ONE hero (In Review: actionable, waiting on a human) and
# four quiet secondary cells, instead of five identical boxes fighting
# for the same amount of attention.
_hero_color = c["amber"] if stats["stories_in_review"] > 0 else c["text_secondary"]

st.markdown(
    f"""
    <div class="sf-metric-strip">
        <div class="sf-metric-hero">
            <div class="sf-metric-value" style="color:{_hero_color};">{stats['stories_in_review']}</div>
            <div class="sf-metric-label">Awaiting Review</div>
        </div>
        <div class="sf-metric-cell">
            <div class="sf-metric-value" style="color:{c['text_primary']};">{stats['total_participants']}</div>
            <div class="sf-metric-label">Participants</div>
        </div>
        <div class="sf-metric-cell">
            <div class="sf-metric-value" style="color:{c['text_primary']};">{stats['total_stories']}</div>
            <div class="sf-metric-label">Total Stories</div>
        </div>
        <div class="sf-metric-cell">
            <div class="sf-metric-value" style="color:{c['green']};">{stats['stories_approved']}</div>
            <div class="sf-metric-label">Approved</div>
        </div>
        <div class="sf-metric-cell">
            <div class="sf-metric-value" style="color:{c['purple']};">{stats['stories_published']}</div>
            <div class="sf-metric-label">Published</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div style="margin-top:2.5rem;"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# MAIN CONTENT — Left: nav cards + pipeline  |  Right: recent activity
# ══════════════════════════════════════════════════════════════════════

left_col, right_col = st.columns([3, 2], gap="large")


# ── LEFT: Quick-nav cards ─────────────────────────────────────────────

with left_col:
    st.markdown('<div class="sf-section-label">Operations</div>', unsafe_allow_html=True)

    # live stat chip per card
    nav_cards = [
        (
            "pages/1_Participants.py", "&#128101;", "Participants",
            "Manage participant profiles, consent, and data",
            f"{stats['total_participants']} participant{'s' if stats['total_participants'] != 1 else ''}",
            c["accent"],
        ),
        (
            "pages/2_Workspace.py", "&#9997;&#65039;", "Workspace",
            "Generate, edit, and submit AI-assisted impact stories",
            f"{stats['stories_draft']} draft{'s' if stats['stories_draft'] != 1 else ''} open",
            c["accent"],
        ),
        (
            "pages/3_Review_Queue.py", "&#128203;", "Review Queue",
            "Review and approve or reject submitted stories",
            f"{stats['stories_in_review']} awaiting review",
            c["amber"] if stats["stories_in_review"] > 0 else c["text_muted"],
        ),
        (
            "pages/4_Repository.py", "&#128218;", "Repository",
            "Search, browse, and publish approved stories",
            f"{stats['total_stories']} total {'story' if stats['total_stories'] == 1 else 'stories'}",
            c["accent"],
        ),
        (
            "pages/5_Exports.py", "&#128228;", "Exports",
            "Download stories as formatted Excel reports",
            f"{stats['stories_approved'] + stats['stories_published']} ready to export",
            c["green"] if (stats["stories_approved"] + stats["stories_published"]) > 0 else c["text_muted"],
        ),
        (
            "pages/6_Batch_Operations.py", "&#128194;", "Batch Operations",
            "CSV import, bulk story generation, and job tracking",
            "1 running" if stats.get("batch_jobs_running", 0) > 0
            else f"{stats.get('batch_jobs_total', 0)} job{'s' if stats.get('batch_jobs_total', 0) != 1 else ''} run",
            c["amber"] if stats.get("batch_jobs_running", 0) > 0 else c["text_muted"],
        ),
    ]

    with st.container(border=True):
        for i, (page_path, icon, name, desc, stat_text, stat_color) in enumerate(nav_cards):
            nc1, nc2, nc3, nc4 = st.columns([0.5, 3.4, 2.0, 1.1])
            with nc1:
                st.markdown(
                    f'<div style="font-size:1.4rem;padding-top:.3rem;opacity:.9;">{icon}</div>',
                    unsafe_allow_html=True,
                )
            with nc2:
                st.markdown(
                    f'<div style="font-size:.92rem;font-weight:600;padding-top:.15rem;'
                    f'color:{c["text_primary"]};">{name}</div>'
                    f'<div style="font-size:.76rem;color:{c["text_muted"]};'
                    f'margin-top:.15rem;line-height:1.5;">{desc}</div>',
                    unsafe_allow_html=True,
                )
            with nc3:
                st.markdown(
                    f'<div style="padding-top:.5rem;">'
                    f'<span style="font-size:.7rem;font-weight:600;color:{stat_color};">'
                    f'{stat_text}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with nc4:
                if st.button("Open", key=f"nav_{name}", use_container_width=True):
                    st.switch_page(page_path)

            if i < len(nav_cards) - 1:
                st.markdown(
                    '<hr style="margin:.55rem 0;border-color:rgba(255,255,255,0.045);">',
                    unsafe_allow_html=True,
                )

    # ── Story Pipeline ────────────────────────────────────────────────
    st.markdown('<div style="margin-top:2.5rem;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-label">Story Pipeline</div>', unsafe_allow_html=True)

    pipeline = [
        ("Draft",     stats["stories_draft"],     c["text_muted"]),
        ("In Review", stats["stories_in_review"], c["amber"]),
        ("Approved",  stats["stories_approved"],  c["green"]),
        ("Published", stats["stories_published"], c["purple"]),
        ("Rejected",  stats["stories_rejected"],  c["red"]),
    ]

    total = max(stats["total_stories"], 1)
    pipe_cols = st.columns(len(pipeline))
    for col, (label, count, color) in zip(pipe_cols, pipeline):
        pct = int((count / total) * 100)
        col.markdown(
            f"""
            <div class="sf-card" style="text-align:center;padding:1.1rem .75rem;">
                <div style="font-size:1.55rem;font-weight:700;
                     color:{color};font-family:'DM Mono',monospace;">{count}</div>
                <div style="font-size:.68rem;color:{c['text_muted']};
                     margin-top:.3rem;font-weight:500;
                     text-transform:uppercase;letter-spacing:.05em;">{label}</div>
                <div style="margin-top:.65rem;height:3px;
                     border-radius:2px;background:{c['border']};">
                    <div style="height:100%;width:{pct}%;
                         background:{color};border-radius:2px;"></div>
                </div>
                <div style="font-size:.68rem;color:{c['text_muted']};
                     margin-top:.35rem;font-family:'DM Mono',monospace;">{pct}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── RIGHT: Recent activity feed ───────────────────────────────────────

with right_col:
    st.markdown('<div class="sf-section-label">Recent Activity</div>', unsafe_allow_html=True)

    if not recent_stories:
        st.markdown(
            f"""
            <div style="border:1.5px dashed {c['border']};border-radius:12px;
                 padding:3rem;text-align:center;margin-top:.25rem;">
                <div style="font-size:1.5rem;margin-bottom:.75rem;">&#10022;</div>
                <div style="font-size:.875rem;font-weight:600;
                     color:{c['text_primary']};margin-bottom:.4rem;">
                    No stories yet
                </div>
                <div style="font-size:.8rem;color:{c['text_muted']};line-height:1.7;">
                    Add a participant, then generate<br>
                    their first story in the Workspace.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="sf-timeline">', unsafe_allow_html=True)
        for s in recent_stories:
            fmt_spec  = STORY_FORMATS.get(s.get("format", ""), {})
            fmt_icon  = fmt_spec.get("icon", "\u2726")
            fmt_label = fmt_spec.get("label", s.get("format", ""))
            wc        = s.get("word_count", 0) or 0
            name      = s.get("participant_name", "Unknown")
            content   = s.get("content") or ""
            preview   = content[:85].strip()
            if len(content) > 85:
                preview += "\u2026"

            # Status colours inline (avoids import of badges for html-only use)
            STATUS_FG = {
                "draft":     c["text_muted"],
                "in_review": c["amber"],
                "approved":  c["green"],
                "published": c["purple"],
                "rejected":  c["red"],
            }
            STATUS_BG = {
                "draft":     c["surface_alt"],
                "in_review": c["amber_soft"],
                "approved":  c["green_soft"],
                "published": c["purple_soft"],
                "rejected":  c["red_soft"],
            }
            st_key = s.get("status", "draft")
            st_fg  = STATUS_FG.get(st_key, c["text_muted"])
            st_bg  = STATUS_BG.get(st_key, c["surface_alt"])
            st_lbl = st_key.replace("_", " ").title()

            st.markdown(
                f"""
                <style>
                .sf-dot-{s['id']}::before {{ background:{st_fg} !important; box-shadow:0 0 0 3px {st_bg} !important; }}
                </style>
                <div class="sf-timeline-item sf-dot-{s['id']}">
                    <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;">
                        <span style="display:inline-flex;align-items:center;
                              padding:.15rem .55rem;border-radius:20px;
                              background:{st_bg};color:{st_fg};
                              font-size:.68rem;font-weight:600;">{st_lbl}</span>
                        <span style="font-size:.73rem;color:{c['text_secondary']};">
                            {fmt_icon} {fmt_label}
                        </span>
                        <span style="font-size:.68rem;color:{c['text_muted']};
                              margin-left:auto;font-family:'DM Mono',monospace;">
                            {wc}w
                        </span>
                    </div>
                    <div style="font-size:.82rem;font-weight:600;
                         color:{c['text_primary']};margin-bottom:.2rem;">{name}</div>
                    <div style="font-size:.75rem;color:{c['text_muted']};
                         line-height:1.5;font-style:italic;">
                        {preview or 'No content yet.'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)  # close .sf-timeline

        st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
        if st.button("View all in Repository", key="nav_repo_recent", use_container_width=True):
            st.switch_page("pages/4_Repository.py")


# ══════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="margin-top:3rem;padding-top:1.25rem;border-top:1px solid {c['border']};
         display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:.72rem;color:{c['text_muted']};">
            <strong style="color:{c['text_secondary']};">StoryForge v3.0</strong>
            &nbsp;&#183;&nbsp; Cloud Counselage Pvt. Ltd.
            &nbsp;&#183;&nbsp; IAC Vision 2030
        </div>
        <div style="font-size:.72rem;color:{c['text_muted']};">
            AI Disclosure: Stories generated with Google Gemini 2.5 Flash.
            Human review required before publication.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)