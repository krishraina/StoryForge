"""
StoryForge — Export Center
──────────────────────────
Tab 1 — By Participant
  Select a participant → see their stories → filter by format/status → download Excel

Tab 2 — Batch Export
  Four preset modes (Approved / Published / Ready to Publish / Full DB)
  Optional format filter → download Excel

Widget key prefix: exp_*
"""

import streamlit as st
from datetime import datetime

from components.theme    import page_config, apply_theme, COLORS
from components.badges   import status_badge, format_badge, participant_options
from services.db_service import (
    get_all_participants,
    get_stories_for_participant,
    get_stories_by_status,
    get_all_stories,
    list_import_batches,
)
from services.export_service import build_excel, make_filename
from core.constants import STORY_FORMATS, STORY_STATUSES
from core.database  import init_db

# ── Boot ──────────────────────────────────────────────────────────────
init_db()
page_config("Exports")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()
c = COLORS


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

def _stat_chip(label: str, value, color: str = None) -> str:
    fg = color or c["text_primary"]
    return (
        f'<div style="background:{c["surface"]};border:1px solid {c["border"]};'
        f'border-radius:10px;padding:.6rem 1rem;text-align:center;">'
        f'<div style="font-size:1.3rem;font-weight:700;color:{fg};">{value}</div>'
        f'<div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;'
        f'color:{c["text_muted"]};margin-top:.15rem;">{label}</div>'
        f'</div>'
    )


def _section_label(text: str):
    st.markdown(
        f'<div class="sf-section-label" style="margin-top:1.25rem;">{text}</div>',
        unsafe_allow_html=True,
    )


def _story_preview_row(s: dict):
    """Single story row in the preview table."""
    fmt_spec = STORY_FORMATS.get(s.get("format", ""), {})
    fmt_icon = fmt_spec.get("icon", "\u2726")
    fmt_lbl  = fmt_spec.get("label", s.get("format", ""))
    wc       = s.get("word_count", 0) or 0
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:.65rem;'
        f'padding:.35rem 0;border-bottom:1px solid {c["border"]};">'
        + status_badge(s.get("status", "draft"))
        + f'<span style="font-size:.8rem;color:{c["text_secondary"]};">'
          f'{fmt_icon} {fmt_lbl}</span>'
        + f'<span style="font-size:.72rem;color:{c["text_muted"]};'
          f'font-family:\'DM Mono\',monospace;margin-left:auto;">'
          f'{wc} words</span>'
        + '</div>',
        unsafe_allow_html=True,
    )


def _no_stories_notice(context: str = ""):
    st.markdown(
        f'<div style="text-align:center;padding:2.5rem;'
        f'border:1.5px dashed {c["border"]};border-radius:12px;'
        f'color:{c["text_muted"]};font-size:.875rem;">'
        f'No stories found{" " + context if context else ""}.<br>'
        f'<span style="font-size:.8rem;">Generate stories in the Workspace first.</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
         margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div>
            <div class="sf-page-title">Exports</div>
            <div class="sf-page-subtitle">Download stories as formatted Excel reports</div>
        </div>
        <div style="font-size:.75rem;color:{c['text_muted']};text-align:right;line-height:1.8;">
            Format: Excel (.xlsx)<br>
            Includes AI disclosure
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick stats banner
all_stories = get_all_stories()
total       = len(all_stories)
approved    = sum(1 for s in all_stories if s.get("status") == "approved")
published   = sum(1 for s in all_stories if s.get("status") == "published")
ready       = approved + published

sc1, sc2, sc3, sc4 = st.columns(4)
sc1.markdown(_stat_chip("Total Stories", total), unsafe_allow_html=True)
sc2.markdown(_stat_chip("Approved", approved, c["green"]), unsafe_allow_html=True)
sc3.markdown(_stat_chip("Published", published, c["purple"]), unsafe_allow_html=True)
sc4.markdown(_stat_chip("Ready to Export", ready, c["accent"]), unsafe_allow_html=True)

st.markdown('<div style="margin-bottom:1.5rem;"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════

tab_participant, tab_batch = st.tabs(["By Participant", "Batch Export"])


# ╔══════════════════════════════════════════════════════════════════════
# TAB 1 — BY PARTICIPANT
# ╚══════════════════════════════════════════════════════════════════════

with tab_participant:
    participants = get_all_participants()

    if not participants:
        _no_stories_notice("— add participants first")
    else:
        # ── Participant selector ──────────────────────────────────────
        _section_label("Participant")

        # FB-03: shared helper builds display labels — unique names pass
        # through, duplicates get a disambiguating suffix.
        p_options = participant_options(participants)
        sel_pid = st.selectbox(
            "Select participant",
            options=list(p_options.keys()),
            format_func=lambda k: p_options[k],
            label_visibility="collapsed",
            key="exp_participant",
        )

        # Load their stories
        p_stories = get_stories_for_participant(sel_pid)
        sel_p     = next((p for p in participants if p["id"] == sel_pid), {})

        if not p_stories:
            st.markdown('<div style="margin-top:.75rem;"></div>', unsafe_allow_html=True)
            _no_stories_notice(f"for {sel_p.get('name', '')}")
        else:
            # ── Story filter options ──────────────────────────────────
            _section_label("Filter stories to include")

            fl1, fl2 = st.columns(2)

            with fl1:
                st.markdown(
                    f'<div style="font-size:.75rem;color:{c["text_muted"]};'
                    f'margin-bottom:.4rem;">Formats</div>',
                    unsafe_allow_html=True,
                )
                present_formats = sorted({s.get("format") for s in p_stories})
                sel_formats = []
                for fmt in present_formats:
                    spec = STORY_FORMATS.get(fmt, {})
                    checked = st.checkbox(
                        f"{spec.get('icon', '')} {spec.get('label', fmt)}",
                        value=True,
                        key=f"exp_fmt_{sel_pid}_{fmt}",
                    )
                    if checked:
                        sel_formats.append(fmt)

            with fl2:
                st.markdown(
                    f'<div style="font-size:.75rem;color:{c["text_muted"]};'
                    f'margin-bottom:.4rem;">Statuses</div>',
                    unsafe_allow_html=True,
                )
                present_statuses = sorted({s.get("status") for s in p_stories})
                sel_statuses = []
                for status in present_statuses:
                    s_cfg  = STORY_STATUSES.get(status, {})
                    s_label = s_cfg.get("label", status.replace("_", " ").title())
                    checked = st.checkbox(
                        s_label,
                        value=True,
                        key=f"exp_status_{sel_pid}_{status}",
                    )
                    if checked:
                        sel_statuses.append(status)

            # Apply filters
            export_stories = [
                s for s in p_stories
                if s.get("format") in sel_formats
                and s.get("status") in sel_statuses
            ]

            # ── Preview ───────────────────────────────────────────────
            _section_label(f"Preview — {len(export_stories)} stories selected")

            if not export_stories:
                st.markdown(
                    f'<div style="font-size:.82rem;color:{c["text_muted"]};'
                    f'font-style:italic;padding:.5rem 0;">'
                    f'No stories match the selected filters.</div>',
                    unsafe_allow_html=True,
                )
            else:
                for s in export_stories:
                    _story_preview_row(s)

                st.markdown('<div style="margin-top:1.25rem;"></div>', unsafe_allow_html=True)

                # ── Download button ───────────────────────────────────
                participant_name = sel_p.get("name", "Participant")
                export_title = (
                    f"{participant_name}  \u00b7  "
                    f"{len(export_stories)} {'story' if len(export_stories)==1 else 'stories'}  \u00b7  "
                    f"Exported {datetime.now().strftime('%d %b %Y')}"
                )

                excel_buf  = build_excel(export_stories, title=export_title)
                filename   = make_filename(f"Participant_{participant_name}")

                dl1, _gap = st.columns([2, 5])
                with dl1:
                    st.download_button(
                        label=f"Download Excel ({len(export_stories)} stories)",
                        data=excel_buf,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"exp_dl_participant_{sel_pid}",
                    )

                st.markdown(
                    f'<div style="font-size:.75rem;color:{c["text_muted"]};'
                    f'margin-top:.4rem;">'
                    f'File: <code style="font-size:.72rem;">{filename}</code></div>',
                    unsafe_allow_html=True,
                )


# ╔══════════════════════════════════════════════════════════════════════
# TAB 2 — BATCH EXPORT
# ╚══════════════════════════════════════════════════════════════════════

with tab_batch:

    # ── Batch mode cards ──────────────────────────────────────────────
    _section_label("Export Mode")

    BATCH_MODES = {
        "approved": {
            "label":   "Approved Stories",
            "desc":    "Stories that have been reviewed and approved — safe to publish.",
            "color":   c["green"],
            "statuses": ["approved"],
        },
        "published": {
            "label":   "Published Stories",
            "desc":    "Stories already marked as published.",
            "color":   c["purple"],
            "statuses": ["published"],
        },
        "ready": {
            "label":   "Ready to Publish",
            "desc":    "Approved + Published stories combined.",
            "color":   c["accent"],
            "statuses": ["approved", "published"],
        },
        "all": {
            "label":   "Full Database",
            "desc":    "Every story regardless of status. Good for internal audits.",
            "color":   c["text_secondary"],
            "statuses": None,   # None = all statuses
        },
    }

    batch_mode = st.radio(
        "Select export mode",
        options=list(BATCH_MODES.keys()),
        format_func=lambda k: BATCH_MODES[k]["label"],
        label_visibility="collapsed",
        horizontal=True,
        key="exp_batch_mode",
    )

    mode_cfg = BATCH_MODES[batch_mode]

    st.markdown(
        f'<div style="font-size:.82rem;color:{c["text_muted"]};'
        f'margin:.4rem 0 1rem 0;">{mode_cfg["desc"]}</div>',
        unsafe_allow_html=True,
    )

    # ── Optional format filter ────────────────────────────────────────
    _section_label("Format Filter (optional)")

    fmt_cols = st.columns(len(STORY_FORMATS))
    batch_formats = []
    for col, (fmt_key, spec) in zip(fmt_cols, STORY_FORMATS.items()):
        with col:
            checked = st.checkbox(
                f"{spec['icon']} {spec['label']}",
                value=True,
                key=f"exp_batch_fmt_{fmt_key}",
            )
            if checked:
                batch_formats.append(fmt_key)

    # ── Optional cohort filter — Phase 7 ────────────────────────────
    _section_label("Import Cohort Filter (optional)")

    import_batches = list_import_batches()
    cohort_options = {"all": "All cohorts"}
    for b in import_batches:
        fallback_summary = f"{b['success_count']} imported"
        summary_text = b.get("summary") or fallback_summary
        cohort_options[b["id"]] = f"Batch #{b['id']} — {b.get('started_at', '')} — {summary_text}"

    sel_cohort = st.selectbox(
        "Limit to a specific CSV import batch",
        options=list(cohort_options.keys()),
        format_func=lambda k: cohort_options[k],
        label_visibility="collapsed",
        key="exp_batch_cohort",
    )

    if not import_batches:
        st.markdown(
            f'<div style="font-size:.75rem;color:{c["text_muted"]};margin-top:-.5rem;">'
            f'No CSV imports yet — run one from Batch Operations to unlock cohort exports.</div>',
            unsafe_allow_html=True,
        )

    # ── Fetch & filter stories ────────────────────────────────────────
    if mode_cfg["statuses"] is None:
        candidate_stories = get_all_stories()
    else:
        candidate_stories = []
        for status in mode_cfg["statuses"]:
            candidate_stories.extend(get_stories_by_status(status))

    batch_stories = [
        s for s in candidate_stories
        if s.get("format") in batch_formats
        and (sel_cohort == "all" or s.get("import_batch_id") == sel_cohort)
    ]

    # ── Summary ───────────────────────────────────────────────────────
    _section_label("Export Preview")

    if not batch_stories:
        _no_stories_notice(f"matching '{mode_cfg['label']}'")
    else:
        # Compact breakdown table
        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.markdown(
            _stat_chip("Stories", len(batch_stories), mode_cfg["color"]),
            unsafe_allow_html=True,
        )
        bm2.markdown(
            _stat_chip(
                "Participants",
                len({s.get("participant_id") for s in batch_stories}),
            ),
            unsafe_allow_html=True,
        )
        bm3.markdown(
            _stat_chip(
                "Total Words",
                f"{sum(s.get('word_count', 0) or 0 for s in batch_stories):,}",
            ),
            unsafe_allow_html=True,
        )
        bm4.markdown(
            _stat_chip(
                "Formats",
                len({s.get("format") for s in batch_stories}),
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)

        # Per-format breakdown (display-only)
        for fmt_key, spec in STORY_FORMATS.items():
            fmt_s = [s for s in batch_stories if s.get("format") == fmt_key]
            if not fmt_s:
                continue
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:.65rem;'
                f'padding:.3rem 0;border-bottom:1px solid {c["border"]};">'
                + format_badge(fmt_key)
                + f'<span style="font-size:.8rem;color:{c["text_secondary"]};">'
                  f'{len(fmt_s)} {"story" if len(fmt_s)==1 else "stories"}</span>'
                + f'<span style="font-size:.72rem;color:{c["text_muted"]};'
                  f'font-family:\'DM Mono\',monospace;margin-left:auto;">'
                  f'{sum(s.get("word_count",0) or 0 for s in fmt_s):,} words</span>'
                + '</div>',
                unsafe_allow_html=True,
            )

        # ── Download ──────────────────────────────────────────────────
        st.markdown('<div style="margin-top:1.25rem;"></div>', unsafe_allow_html=True)

        cohort_suffix = f"_{cohort_options[sel_cohort].split(' ')[1]}" if sel_cohort != "all" else ""
        export_title = (
            f"{mode_cfg['label']}"
            + (f"  \u00b7  {cohort_options[sel_cohort]}" if sel_cohort != "all" else "")
            + f"  \u00b7  {len(batch_stories)} stories  \u00b7  "
            f"Exported {datetime.now().strftime('%d %b %Y')}"
        )
        excel_buf = build_excel(batch_stories, title=export_title)
        filename  = make_filename(mode_cfg["label"].replace(" ", "_") + cohort_suffix)

        dl_col, _gap = st.columns([2, 5])
        with dl_col:
            st.download_button(
                label=f"Download Excel ({len(batch_stories)} stories)",
                data=excel_buf,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"exp_dl_batch_{batch_mode}",
            )

        st.markdown(
            f'<div style="font-size:.75rem;color:{c["text_muted"]};margin-top:.4rem;">'
            f'File: <code style="font-size:.72rem;">{filename}</code></div>',
            unsafe_allow_html=True,
        )