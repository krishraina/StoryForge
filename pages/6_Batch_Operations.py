"""
StoryForge — Batch Operations  (Phase 7)
─────────────────────────────────────────
Tab 1 — Import        CSV upload → validate → bulk insert participants
Tab 2 — Generate       Multi-participant × multi-format story generation
Tab 3 — Jobs           Progress dashboard — every import/generate run
Tab 4 — Analytics      Cohort-level rollups across programs/domains/formats

Widget key prefix: bo_*
"""

import time
from datetime import datetime

import streamlit as st

from components.theme import page_config, apply_theme, COLORS
from components.badges import format_badge, participant_options, format_options
from core.config import settings
from core.constants import STORY_FORMATS
from core.database import init_db
from services.db_service import (
    get_all_participants,
    get_all_stories,
    list_batch_jobs,
    get_latest_generate_job,
    mark_stale_running_jobs_failed,
    bulk_update_story_status,
    get_batch_draft_stories,
    create_batch_job,
    update_batch_job,
    list_import_batches,
    get_participants_by_batch_id,
    count_stories_for_batch,
    count_stories_for_generate_job,
    get_story_counts_for_batch,
    get_stories_for_batch,
    delete_import_batch,
)
from core.timeutils import display_datetime
from services.batch_service import (
    parse_participant_csv,
    import_participants,
    build_batch_queue,
    generate_next_batch_unit,
    ALL_COLUMNS,
)
from services.gemini_service import is_api_configured

# ── Boot ──────────────────────────────────────────────────────────────
init_db()
# Mark any jobs still in status='running' from a previous server session
# as failed before rendering anything. This is the second line of defence
# after the per-render state-recovery check in Tab 2 — it fixes the DB
# itself so the Jobs tab also shows correct status after a server restart.
mark_stale_running_jobs_failed()
page_config("Batch Operations")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()
c = COLORS


# ══════════════════════════════════════════════════════════════════════
# HELPERS
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


_JOB_STATUS_CFG = {
    "pending":   (c["text_muted"],  c["surface_alt"]),
    "running":   (c["accent"],      c["accent_soft"]),
    "completed": (c["green"],       c["green_soft"]),
    "partial":   (c["amber"],       c["amber_soft"]),
    "failed":    (c["red"],         c["red_soft"]),
}


def _job_status_badge(status: str) -> str:
    fg, bg = _JOB_STATUS_CFG.get(status, (c["text_muted"], c["surface_alt"]))
    return (
        f'<span style="display:inline-flex;align-items:center;padding:.18rem .6rem;'
        f'border-radius:20px;background:{bg};color:{fg};font-size:.72rem;'
        f'font-weight:600;text-transform:capitalize;">{status}</span>'
    )


def _progress_bar_html(pct: int, color: str) -> str:
    return (
        f'<div style="height:6px;border-radius:3px;background:{c["border"]};margin-top:.4rem;">'
        f'<div style="height:100%;width:{pct}%;background:{color};border-radius:3px;"></div>'
        f'</div>'
    )


# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div class="sf-page-title">🗂 Batch Operations</div>
        <div class="sf-page-subtitle">Import participants, generate stories, and track jobs at scale</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_import, tab_generate, tab_jobs, tab_analytics = st.tabs(
    ["📥 Import", "⚡ Generate", "📈 Jobs", "📊 Analytics"]
)


# ╔══════════════════════════════════════════════════════════════════════
# TAB 1 — IMPORT
# ╚══════════════════════════════════════════════════════════════════════

with tab_import:
    st.markdown(
        f'<div style="font-size:.85rem;color:{c["text_muted"]};margin-bottom:1rem;">'
        f'Upload a CSV of participants. Only <strong>name</strong> is required — '
        f'everything else is optional and can be filled in later from the Participants page.'
        f'</div>',
        unsafe_allow_html=True,
    )

    template_csv = ",".join(ALL_COLUMNS) + "\n" + \
        "Jane Doe,jane@example.com,Global Professional Internship (GPI),Web Development," \
        "Started with no coding background.,Built and shipped a full-stack app.," \
        "Balancing the program with a full-time job.,Placed as a junior developer.,full," \
        "https://linkedin.com/in/janedoe\n"

    dl_col, _gap = st.columns([2, 5])
    with dl_col:
        st.download_button(
            "Download CSV template",
            data=template_csv,
            file_name="storyforge_participant_template.csv",
            mime="text/csv",
            use_container_width=True,
            key="bo_template_dl",
        )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload participant CSV", type=["csv"], key="bo_csv_uploader",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        file_bytes = uploaded.getvalue()

        # Re-parse only when a new file is uploaded (avoid re-validating
        # against the DB on every widget interaction in this tab).
        if st.session_state.get("bo_csv_sig") != (uploaded.name, len(file_bytes)):
            valid_rows, row_errors = parse_participant_csv(file_bytes)
            st.session_state.bo_csv_rows = valid_rows
            st.session_state.bo_csv_errors = row_errors
            st.session_state.bo_csv_sig = (uploaded.name, len(file_bytes))

        valid_rows = st.session_state.get("bo_csv_rows", [])
        row_errors = st.session_state.get("bo_csv_errors", [])

        _section_label("Validation Summary")
        sc1, sc2 = st.columns(2)
        sc1.markdown(_stat_chip("Valid rows", len(valid_rows), c["green"]), unsafe_allow_html=True)
        sc2.markdown(
            _stat_chip("Rows with errors", len(row_errors), c["red"] if row_errors else c["text_muted"]),
            unsafe_allow_html=True,
        )

        if row_errors:
            with st.expander(f"View {len(row_errors)} error(s)", expanded=False):
                for e in row_errors:
                    st.markdown(
                        f'<div style="font-size:.8rem;color:{c["text_secondary"]};'
                        f'padding:.3rem 0;border-bottom:1px solid {c["border"]};">'
                        f'<strong style="color:{c["red"]};">Row {e["row"]}</strong> '
                        f'({e["name"]}) — {e["error"]}</div>',
                        unsafe_allow_html=True,
                    )

        if valid_rows:
            _section_label(f"Preview — {len(valid_rows)} participant(s) ready to import")
            preview = valid_rows[:10]
            st.markdown(
                f'<div style="font-size:.75rem;color:{c["text_muted"]};margin-bottom:.5rem;">'
                f'Showing {len(preview)} of {len(valid_rows)}</div>',
                unsafe_allow_html=True,
            )
            for row in preview:
                st.markdown(
                    f'<div style="display:flex;gap:.75rem;padding:.4rem 0;'
                    f'border-bottom:1px solid {c["border"]};align-items:center;">'
                    f'<span style="font-size:.83rem;font-weight:600;color:{c["text_primary"]};'
                    f'min-width:160px;">{row["name"]}</span>'
                    f'<span style="font-size:.75rem;color:{c["text_muted"]};">{row.get("email") or "—"}</span>'
                    f'<span style="font-size:.75rem;color:{c["text_secondary"]};margin-left:auto;">'
                    f'{row.get("program") or "—"}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div style="margin-top:1.25rem;"></div>', unsafe_allow_html=True)
            ic1, _gap = st.columns([2, 5])
            with ic1:
                if st.button(
                    f"Import {len(valid_rows)} participant(s)",
                    use_container_width=True,
                    key="bo_import_btn",
                ):
                    with st.spinner("Importing…"):
                        result = import_participants(valid_rows)
                    st.success(
                        f"Imported {result['success']} participant(s)."
                        + (f" {len(result['errors'])} failed during insert — see Jobs tab for the log."
                           if result["errors"] else "")
                    )
                    st.session_state.bo_csv_rows = []
                    st.session_state.bo_csv_errors = []
                    st.session_state.bo_csv_sig = None
        elif not row_errors:
            st.info("No rows found in this file.")

    # ── Recent Imports ────────────────────────────────────────────────
    st.markdown(
        f'<hr style="border-color:{c["border"]};margin:2rem 0 1.25rem 0;">',
        unsafe_allow_html=True,
    )
    _section_label("Recent Imports")

    _recent_batches = list_import_batches()

    if not _recent_batches:
        st.markdown(
            f'<div style="font-size:.82rem;color:{c["text_muted"]};'
            f'font-style:italic;padding:.35rem 0;">No import batches yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Refinement 4 — disable all Delete buttons while any confirmation
        # is open or a deletion is actively running; prevents opening
        # multiple confirmations simultaneously and prevents double-clicks.
        _any_confirm_open = st.session_state.get("bo_confirm_delete_batch") is not None
        _deleting         = st.session_state.get("bo_deleting_batch", False)

        for _b in _recent_batches:
            _bid      = _b["id"]
            _p_count  = len(get_participants_by_batch_id(_bid))
            _imported = display_datetime(_b.get("started_at") or "")

            with st.container(border=True):
                # ── Metadata + delete button ──────────────────────────
                _rm1, _rm2 = st.columns([4, 1])
                with _rm1:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:.65rem;'
                        f'flex-wrap:wrap;">'
                        f'<span style="font-size:.88rem;font-weight:700;'
                        f'color:{c["text_primary"]};">Batch #{_bid}</span>'
                        f'<span style="font-size:.75rem;color:{c["text_muted"]};">'
                        f'{_imported}</span>'
                        f'<span style="display:inline-flex;align-items:center;'
                        f'padding:.1rem .45rem;border-radius:10px;'
                        f'background:{c["green_soft"]};color:{c["green"]};'
                        f'font-size:.68rem;font-weight:600;">'
                        f'{_p_count} participant{"s" if _p_count != 1 else ""} imported'
                        f'</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with _rm2:
                    if st.button(
                        "🗑 Delete",
                        key=f"bo_del_batch_{_bid}",
                        use_container_width=True,
                        disabled=_any_confirm_open or _deleting,
                    ):
                        st.session_state["bo_confirm_delete_batch"] = _bid
                        st.rerun()

                # ── F-06: Operational summary ──────────────────────────
                # Reuses get_story_counts_for_batch() (already existed —
                # previously only rendered inside the delete-confirmation
                # panel) and the new get_stories_for_batch() to compute
                # participant coverage. No schema change, no new services.
                _status_counts_f06 = get_story_counts_for_batch(_bid)
                _total_stories_f06 = sum(_status_counts_f06.values())
                _batch_stories_f06 = get_stories_for_batch(_bid)
                _covered_pids_f06  = {s["participant_id"] for s in _batch_stories_f06}
                _coverage_pct_f06  = (
                    round(len(_covered_pids_f06) / _p_count * 100) if _p_count else 0
                )

                _STATUS_LABELS_F06 = {
                    "draft": "Draft", "in_review": "In Review",
                    "approved": "Approved", "published": "Published",
                    "rejected": "Rejected",
                }
                _STATUS_COLORS_F06 = {
                    "draft":     (c["text_muted"], c["surface_alt"]),
                    "in_review": (c["amber"],      c["amber_soft"]),
                    "approved":  (c["green"],      c["green_soft"]),
                    "published": (c["purple"],     c["purple_soft"]),
                    "rejected":  (c["red"],        c["red_soft"]),
                }
                _chips_f06 = "".join(
                    f'<span style="display:inline-flex;align-items:center;'
                    f'padding:.1rem .5rem;border-radius:12px;margin-right:.4rem;'
                    f'background:{_STATUS_COLORS_F06.get(_sk, (c["text_muted"], c["surface_alt"]))[1]};'
                    f'color:{_STATUS_COLORS_F06.get(_sk, (c["text_muted"], c["surface_alt"]))[0]};'
                    f'font-size:.68rem;font-weight:600;">{_sv} {_STATUS_LABELS_F06.get(_sk, _sk)}</span>'
                    for _sk, _sv in _status_counts_f06.items() if _sv > 0
                ) or (
                    f'<span style="font-size:.75rem;color:{c["text_muted"]};'
                    f'font-style:italic;">no stories generated yet</span>'
                )

                st.markdown(
                    f'<div style="margin-top:.6rem;padding-top:.55rem;'
                    f'border-top:1px solid {c["border"]};display:flex;'
                    f'align-items:center;gap:.6rem;flex-wrap:wrap;">'
                    f'<span style="font-size:.72rem;color:{c["text_muted"]};">'
                    f'{_total_stories_f06} stor{"y" if _total_stories_f06 == 1 else "ies"} '
                    f'&nbsp;\u00b7&nbsp; {len(_covered_pids_f06)}/{_p_count} participants covered '
                    f'({_coverage_pct_f06}%)</span>'
                    f'{_chips_f06}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── F-06: Batch detail view + centralized actions ──────
                # NOTE: "Open Repository" / "Open Review Queue" are plain
                # page switches, not batch-filtered views — Repository and
                # Review Queue are frozen per the ticket scope and were not
                # modified to accept a batch filter.
                with st.expander("View participants / batch actions", expanded=False):
                    _batch_participants_f06 = get_participants_by_batch_id(_bid)
                    if not _batch_participants_f06:
                        st.markdown(
                            f'<div style="font-size:.78rem;color:{c["text_muted"]};'
                            f'font-style:italic;">No participants remain in this batch.</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        for _bp in _batch_participants_f06:
                            _bp_stories = [
                                s for s in _batch_stories_f06
                                if s["participant_id"] == _bp["id"]
                            ]
                            _bp_status = "".join(
                                f'<span style="font-size:.66rem;color:'
                                f'{_STATUS_COLORS_F06.get(_s["status"], (c["text_muted"], c["surface_alt"]))[0]};'
                                f'margin-right:.35rem;">'
                                f'{_STATUS_LABELS_F06.get(_s["status"], _s["status"])}'
                                f'&nbsp;{STORY_FORMATS.get(_s["format"], {}).get("icon", "")}</span>'
                                for _s in _bp_stories
                            ) or (
                                f'<span style="font-size:.66rem;color:{c["text_muted"]};'
                                f'font-style:italic;">no stories</span>'
                            )
                            st.markdown(
                                f'<div style="display:flex;align-items:center;gap:.5rem;'
                                f'padding:.3rem 0;border-bottom:1px solid {c["border"]};">'
                                f'<span style="font-size:.8rem;color:{c["text_primary"]};'
                                f'min-width:160px;">{_bp["name"]}</span>'
                                f'<span style="margin-left:auto;">{_bp_status}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    st.markdown('<div style="margin-top:.75rem;"></div>', unsafe_allow_html=True)
                    _ba1, _ba2, _ba3 = st.columns(3)
                    with _ba1:
                        if st.button(
                            "⚡ Select for Generate",
                            key=f"bo_batch_select_gen_{_bid}",
                            use_container_width=True,
                            help="Preselects this batch's eligible participants in the Generate tab above.",
                        ):
                            _eligible_ids_f06 = [
                                p["id"] for p in _batch_participants_f06
                                if p.get("consent_level") in ("full", "anonymized", "internal")
                            ]
                            st.session_state["bo_pid_multiselect"] = _eligible_ids_f06
                            st.success(
                                f"{len(_eligible_ids_f06)} participant(s) preselected \u2014 "
                                f"switch to the Generate tab above."
                            )
                    with _ba2:
                        if st.button(
                            "📚 Open Repository",
                            key=f"bo_batch_open_repo_{_bid}",
                            use_container_width=True,
                        ):
                            st.switch_page("pages/4_Repository.py")
                    with _ba3:
                        if st.button(
                            "📋 Open Review Queue",
                            key=f"bo_batch_open_rq_{_bid}",
                            use_container_width=True,
                        ):
                            st.switch_page("pages/3_Review_Queue.py")

                # ── Confirmation panel (armed state) ──────────────────
                if st.session_state.get("bo_confirm_delete_batch") == _bid:

                    # Refinement 3 — empty batch guard
                    if _p_count == 0:
                        st.markdown(
                            f'<div style="margin-top:.65rem;'
                            f'background:{c["amber_soft"]};'
                            f'border:1px solid {c["amber"]};border-radius:8px;'
                            f'padding:.7rem 1rem;font-size:.82rem;'
                            f'color:{c["amber"]};">'
                            f'⚠&nbsp; This batch no longer contains participants. '
                            f'Nothing to delete.'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            '<div style="margin-top:.5rem;"></div>',
                            unsafe_allow_html=True,
                        )
                        _ec, _ = st.columns([2, 5])
                        with _ec:
                            if st.button(
                                "Dismiss",
                                key=f"bo_del_empty_{_bid}",
                                use_container_width=True,
                            ):
                                st.session_state["bo_confirm_delete_batch"] = None
                                st.rerun()

                    else:
                        # Refinement 2 — editorial summary with per-status breakdown
                        _status_counts = get_story_counts_for_batch(_bid)
                        _status_order  = [
                            "draft", "in_review", "approved", "published", "rejected"
                        ]
                        _status_labels = {
                            "draft":     "Draft",
                            "in_review": "In Review",
                            "approved":  "Approved",
                            "published": "Published",
                            "rejected":  "Rejected",
                        }
                        _status_colors = {
                            "draft":     c["text_muted"],
                            "in_review": c["amber"],
                            "approved":  c["green"],
                            "published": c["purple"],
                            "rejected":  c["red"],
                        }
                        _total_stories = sum(_status_counts.values())

                        _story_rows = ""
                        for _st in _status_order:
                            _cnt = _status_counts.get(_st, 0)
                            if _cnt == 0:
                                continue
                            _story_rows += (
                                f'<div style="display:flex;justify-content:'
                                f'space-between;padding:.15rem 0;">'
                                f'<span style="color:{c["text_muted"]};'
                                f'font-size:.8rem;">&nbsp;&nbsp;'
                                f'{_status_labels[_st]}</span>'
                                f'<span style="font-weight:600;'
                                f'color:{_status_colors[_st]};font-size:.8rem;">'
                                f'{_cnt}</span>'
                                f'</div>'
                            )

                        # Refinement 6 — strengthened confirmation copy
                        st.markdown(
                            f'<div style="margin-top:.75rem;'
                            f'background:{c["red_soft"]};'
                            f'border:1px solid {c["red"]};border-radius:8px;'
                            f'padding:.85rem 1rem;">'
                            f'<div style="font-size:.9rem;font-weight:700;'
                            f'color:{c["red"]};margin-bottom:.75rem;">'
                            f'⚠ Delete Batch #{_bid}?</div>'
                            # Participants row
                            f'<div style="display:flex;justify-content:space-between;'
                            f'padding:.15rem 0;'
                            f'border-bottom:1px solid {c["border"]};'
                            f'margin-bottom:.4rem;">'
                            f'<span style="font-size:.82rem;font-weight:600;'
                            f'color:{c["text_secondary"]};">Participants</span>'
                            f'<span style="font-size:.82rem;font-weight:700;'
                            f'color:{c["text_primary"]};">{_p_count}</span>'
                            f'</div>'
                            # Stories header
                            f'<div style="font-size:.78rem;font-weight:600;'
                            f'color:{c["text_secondary"]};margin-bottom:.2rem;">'
                            f'Stories</div>'
                            + _story_rows +
                            # Story total
                            f'<div style="display:flex;justify-content:space-between;'
                            f'padding:.2rem 0;border-top:1px solid {c["border"]};'
                            f'margin-top:.35rem;">'
                            f'<span style="font-size:.8rem;color:{c["text_muted"]};">'
                            f'Total</span>'
                            f'<span style="font-size:.8rem;font-weight:700;'
                            f'color:{c["text_primary"]};">{_total_stories}</span>'
                            f'</div>'
                            # Permanence warning
                            f'<div style="margin-top:.75rem;padding-top:.6rem;'
                            f'border-top:1px solid {c["border"]};'
                            f'font-size:.78rem;color:{c["text_secondary"]};'
                            f'line-height:1.6;">'
                            f'⚠&nbsp; This action <strong>permanently deletes</strong> '
                            f'all participants and associated stories — including '
                            f'approved and published content.<br>'
                            f'<strong>This cannot be undone.</strong>'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            '<div style="margin-top:.65rem;"></div>',
                            unsafe_allow_html=True,
                        )
                        _dc1, _dc2, _gap = st.columns([2, 2, 3])
                        with _dc1:
                            # Refinement 4 — Cancel disabled while deletion runs
                            if st.button(
                                "Cancel",
                                key=f"bo_del_cancel_{_bid}",
                                use_container_width=True,
                                disabled=_deleting,
                            ):
                                st.session_state["bo_confirm_delete_batch"] = None
                                st.rerun()
                        with _dc2:
                            # Refinement 4 — Confirm disabled while deletion runs
                            if st.button(
                                "Confirm Delete",
                                key=f"bo_del_confirm_{_bid}",
                                use_container_width=True,
                                disabled=_deleting,
                            ):
                                st.session_state["bo_deleting_batch"] = True
                                try:
                                    _res = delete_import_batch(_bid)
                                    st.session_state["bo_confirm_delete_batch"] = None
                                    st.session_state["bo_deleting_batch"] = False
                                    # BT-11: invalidate the CSV parse cache so that
                                    # re-uploading the same file after deletion triggers
                                    # a fresh parse + fresh email_exists() DB queries.
                                    # Without this, the sig matches the stale cached
                                    # validation (produced while participants were still
                                    # in the DB) and every email reports as "already
                                    # registered" even though the DB is now clean.
                                    st.session_state["bo_csv_sig"]    = None
                                    st.session_state["bo_csv_rows"]   = []
                                    st.session_state["bo_csv_errors"] = []
                                    st.success(
                                        f"✅ Batch #{_bid} deleted successfully — "
                                        f"{_res['participants_deleted']} participant(s) removed, "
                                        f"{_res['stories_deleted']} story/stories removed."
                                    )
                                    st.rerun()
                                except Exception as _exc:
                                    st.session_state["bo_deleting_batch"] = False
                                    st.error(f"Delete failed: {_exc}")


# ╔══════════════════════════════════════════════════════════════════════
# TAB 2 — BULK GENERATE
# ╚══════════════════════════════════════════════════════════════════════

with tab_generate:

    # ── State recovery — reconcile bo_running against the DB ──────────
    # bo_running is a pure session-state boolean. If the server restarts,
    # the browser reloads, or the job is interrupted mid-queue, the code
    # that sets it back to False never runs. At the top of every render
    # we check whether there is any remaining work (bo_pending = initial
    # two-run payload; bo_pending_queue = active per-rerun work queue).
    # If neither is set while bo_running is True, the lock is stale and
    # we release it — but only when the DB job is also in a terminal state.
    _TERMINAL_STATUSES = {"completed", "partial", "failed", "cancelled"}
    _latest_gen_job = get_latest_generate_job()
    if st.session_state.get("bo_running", False):
        _has_work = (
            st.session_state.get("bo_pending")
            or st.session_state.get("bo_pending_queue")
        )
        if not _has_work:
            if _latest_gen_job is None or _latest_gen_job.get("status") in _TERMINAL_STATUSES:
                st.session_state.bo_running = False
                st.session_state.bo_pending = None
                st.session_state.bo_pending_queue = None

    # Resolved value used everywhere below — single source of truth.
    bo_running = st.session_state.get("bo_running", False)

    if not is_api_configured():
        st.error(
            "**Gemini API key not configured.** "
            "Add `GEMINI_API_KEY` to your `.env` file and restart the app."
        )
    else:
        participants = get_all_participants()

        if not participants:
            st.markdown(
                f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">'
                f'No participants yet. Import some in the <strong>Import</strong> tab first.</div>',
                unsafe_allow_html=True,
            )
        else:
            eligible = [p for p in participants if p.get("consent_level") in
                        ("full", "anonymized", "internal")]
            skipped = len(participants) - len(eligible)

            # ── Participant Source radio ──────────────────────────────
            # Look up import batches BEFORE drawing the radio, so we know
            # whether "Latest Import Batch" is even a valid option this
            # render — this is what lets us disable it (Case 2) instead of
            # discovering "no batches" only after the user has selected it.
            _import_batches = list_import_batches()
            _has_import_batch = bool(_import_batches)

            _section_label("Participant Source")

            if not _has_import_batch:
                # ── Case 2: no import batches exist at all ─────────────
                st.markdown(
                    f'<div style="font-size:.78rem;color:{c["text_muted"]};margin-bottom:.5rem;">'
                    f'No import batches available. Please import participants first.</div>',
                    unsafe_allow_html=True,
                )
                st.radio(
                    "Participant source",
                    options=["latest_batch", "all_eligible"],
                    format_func=lambda k: (
                        "Latest Import Batch (unavailable)" if k == "latest_batch"
                        else "All Eligible Participants"
                    ),
                    index=1,
                    horizontal=True,
                    disabled=True,
                    label_visibility="collapsed",
                    key="bo_p_source_disabled",
                )
                p_source = "all_eligible"
                source_pool = eligible
            else:
                p_source = st.radio(
                    "Participant source",
                    options=["latest_batch", "all_eligible"],
                    format_func=lambda k: (
                        "Latest Import Batch" if k == "latest_batch"
                        else "All Eligible Participants"
                    ),
                    index=1,
                    horizontal=True,
                    disabled=bo_running,
                    label_visibility="collapsed",
                    key="bo_p_source",
                )

                # Resolve which participant pool to use
                if p_source == "latest_batch":
                    _latest_import = _import_batches[0]
                    _batch_ps = get_participants_by_batch_id(_latest_import["id"])
                    source_pool = [
                        p for p in _batch_ps
                        if p.get("consent_level") in ("full", "anonymized", "internal")
                    ]

                    # ── Case 1: show full batch metadata up front ──────
                    _imported_at = _latest_import.get("started_at") or "—"
                    st.markdown(
                        f'<div style="font-size:.78rem;color:{c["text_muted"]};'
                        f'margin-top:.4rem;padding:.6rem .8rem;background:{c["surface_alt"]};'
                        f'border:1px solid {c["border"]};border-radius:8px;line-height:1.7;">'
                        f'<strong style="color:{c["text_secondary"]};">Batch #{_latest_import["id"]}</strong>'
                        f'&nbsp;·&nbsp;Imported {_imported_at}<br>'
                        f'{len(_batch_ps)} participant(s) imported '
                        f'&nbsp;·&nbsp; {len(source_pool)} eligible for generation'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # ── Case 3: batch exists and is selected, but resolves
                    # to zero eligible participants (e.g. every imported
                    # participant has consent_level='none'). This is a
                    # genuine fallback, not a "no batches at all" state —
                    # so it gets its own explicit message rather than
                    # silently behaving like All Eligible was chosen.
                    if not source_pool:
                        st.markdown(
                            f'<div style="font-size:.78rem;color:{c["amber"]};margin-top:.4rem;">'
                            f'No recent import batch found.<br>Using All Eligible Participants.</div>',
                            unsafe_allow_html=True,
                        )
                        source_pool = eligible
                else:
                    source_pool = eligible

            # ── Participants multiselect ───────────────────────────────
            _section_label("Participants")
            if skipped:
                st.markdown(
                    f'<div style="font-size:.78rem;color:{c["text_muted"]};margin-bottom:.5rem;">'
                    f'{skipped} participant(s) excluded — no consent on file.</div>',
                    unsafe_allow_html=True,
                )

            # FB-03: shared helper builds display labels — unique names pass
            # through, duplicates get a disambiguating suffix.
            p_options = participant_options(source_pool)
            _all_eligible_ids = list(p_options.keys())

            # BT-10 fix: Participant Source (Latest Import ↔ All Eligible)
            # changes the available participant pool, but the "Select all"
            # checkbox has no way to know that on its own — it only reacts
            # to being clicked (via _apply_select_all's on_change below).
            # Without this, switching source while Select All is checked
            # leaves bo_pid_multiselect holding the OLD source's id list,
            # so the checkbox says "all selected" while the multiselect
            # is actually stale — checkbox and multiselect fall out of sync.
            #
            # Fix: track the source used on the previous render. If it
            # changed on this render AND Select All is currently on,
            # resync bo_pid_multiselect to the NEW source's full id list —
            # written directly into session_state before the multiselect
            # widget below is instantiated, same pre-instantiation-write
            # pattern _apply_select_all already relies on for BT-03.
            # If Select All is off, existing behavior is untouched.
            if st.session_state.get("bo_prev_p_source") != p_source:
                if st.session_state.get("bo_select_all"):
                    st.session_state["bo_pid_multiselect"] = list(_all_eligible_ids)
                st.session_state["bo_prev_p_source"] = p_source

            # BT-03 fix: st.multiselect's `default=` is silently ignored on
            # every render after the widget's key first exists in session
            # state — so toggling the "Select all" checkbox and recomputing
            # a `default=` value has no effect once the user has interacted
            # with the page at all. The only way to actually change a keyed
            # widget's value after that point is to write directly into its
            # session-state key. on_change runs BEFORE the rest of the
            # script body on the rerun it triggers, so by the time
            # st.multiselect() below is instantiated, its session-state
            # value has already been overwritten — this is what makes the
            # override stick instead of being ignored like `default=` was.
            def _apply_select_all():
                if st.session_state.get("bo_select_all"):
                    st.session_state["bo_pid_multiselect"] = list(_all_eligible_ids)
                else:
                    st.session_state["bo_pid_multiselect"] = []

            st.checkbox(
                "Select all eligible participants",
                key="bo_select_all",
                disabled=bo_running,
                on_change=_apply_select_all,
                args=(),
            )

            sel_pids = st.multiselect(
                "Select participants to generate for",
                options=_all_eligible_ids,
                format_func=lambda k: p_options[k],
                label_visibility="collapsed",
                key="bo_pid_multiselect",
                disabled=bo_running,
            )

            # ── Formats multiselect ───────────────────────────────────
            _section_label("Formats")
            # FB-03: shared helper replaces the locally duplicated {icon label} dict
            fmt_labels = format_options()
            sel_formats = st.multiselect(
                "Select formats to generate",
                options=list(fmt_labels.keys()),
                default=["linkedin"],
                format_func=lambda k: fmt_labels[k],
                label_visibility="collapsed",
                key="bo_fmt_multiselect",
                disabled=bo_running,
            )

            # ── Generation Mode radio ─────────────────────────────────
            _section_label("Generation Mode")
            gen_mode = st.radio(
                "Generation mode",
                options=["skip_existing", "create_new", "replace_draft"],
                format_func=lambda k: {
                    "skip_existing": "Skip Existing",
                    "create_new":    "Create New Versions",
                    "replace_draft": "Replace Latest Draft",
                }[k],
                index=1,
                horizontal=True,
                disabled=bo_running,
                label_visibility="collapsed",
                key="bo_gen_mode",
            )

            # ── Run Summary ───────────────────────────────────────────
            total_units = len(sel_pids) * len(sel_formats)
            est_seconds = max(total_units - 1, 0) * 2.5

            _section_label("Run Summary")
            rc1, rc2, rc3 = st.columns(3)
            rc1.markdown(_stat_chip("Participants", len(sel_pids)), unsafe_allow_html=True)
            rc2.markdown(_stat_chip("Formats", len(sel_formats)), unsafe_allow_html=True)
            rc3.markdown(
                _stat_chip("Generations", total_units, c["accent"] if total_units else None),
                unsafe_allow_html=True,
            )
            if total_units and not bo_running:
                st.markdown(
                    f'<div style="font-size:.75rem;color:{c["text_muted"]};margin-top:.5rem;">'
                    f'Estimated time: ~{int(est_seconds // 60)}m {int(est_seconds % 60)}s '
                    f'(sequential calls, paced to respect Gemini rate limits)</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div style="margin-top:1.25rem;"></div>', unsafe_allow_html=True)

            # ── In-progress banner — only shown while actually running ─
            if bo_running:
                st.markdown(
                    f'<div style="background:{c["surface_alt"]};border:1px solid {c["border"]};'
                    f'border-left:3px solid {c["accent"]};border-radius:0 8px 8px 0;'
                    f'padding:.75rem 1rem;font-size:.85rem;color:{c["text_secondary"]};">'
                    f'⏳ <strong>Generation in progress…</strong> '
                    f'Controls are locked until this run finishes.</div>',
                    unsafe_allow_html=True,
                )

            # ── Generate button ───────────────────────────────────────
            can_run = bool(sel_pids) and bool(sel_formats) and not bo_running
            run_clicked = st.button(
                f"⚡ Generate {total_units} stories" if total_units else "⚡ Generate Stories",
                disabled=not can_run,
                use_container_width=True,
                key="bo_generate_btn",
            )

            # ── F-02: Three-phase state machine ───────────────────────
            #
            # Run N   — click → store bo_pending + bo_running → rerun()
            # Run N+1 — bo_pending set, bo_pending_queue None → Phase A:
            #           build queue, create batch_job, populate queue state,
            #           clear bo_pending → rerun()
            # Run N+2…M — bo_pending_queue set → Phase B:
            #           pop one unit, call generate_next_batch_unit(),
            #           update counters + DB, rerun()
            # Phase C (cancel or empty queue) → finalise batch_job,
            #           store bo_last_result, unlock UI → rerun()
            #
            # Cancel button on_click sets bo_cancel_requested = True.
            # The flag is checked at the top of Phase B on the NEXT rerun,
            # after the current in-flight Gemini call finishes naturally —
            # identical pattern to F-01 (Workspace Cancel Generation).
            if run_clicked and can_run:
                # Clear any previous result banner before the new run.
                st.session_state.bo_last_result  = None
                st.session_state.bo_last_progress_summary = None  # P-16
                st.session_state.bo_status_log   = []
                st.session_state.bo_pending = {
                    "pids":     list(sel_pids),
                    "formats":  list(sel_formats),
                    "gen_mode": gen_mode,
                }
                st.session_state.bo_running = True
                st.rerun()

            _pending = st.session_state.get("bo_pending")
            _queue   = st.session_state.get("bo_pending_queue")

            # ── PHASE A: Queue initialization (runs once on N+1) ──────────
            if bo_running and _pending and _queue is None:
                with st.spinner("Preparing batch queue…"):
                    selected_participants = [
                        p for p in source_pool if p["id"] in _pending["pids"]
                    ]
                    run_formats  = _pending["formats"]
                    run_gen_mode = _pending["gen_mode"]
                    queue, skip_count = build_batch_queue(
                        selected_participants, run_formats, run_gen_mode,
                    )

                total_units = len(queue) + skip_count
                # F-03: processable_units = units that will actually go through
                # Gemini (queue only — skip_count units never enter the queue at
                # all, per build_batch_queue()'s own pre-filtering). The progress
                # bar and "current unit" counter must be measured against this,
                # not total_units, or a skip_existing run can never visually
                # reach 100% even though it completes correctly.
                processable_units  = len(queue)
                total_participants = len({p["id"] for p, _f in queue})
                job_id = create_batch_job("generate", total_items=total_units)

                st.session_state.bo_pending_queue   = queue
                st.session_state.bo_job_id          = job_id
                st.session_state.bo_active_gen_mode = run_gen_mode   # not bo_gen_mode — that key belongs to the radio widget
                st.session_state.bo_done_count      = 0
                st.session_state.bo_total_units    = total_units
                st.session_state.bo_processable_units  = processable_units    # F-03
                st.session_state.bo_total_participants = total_participants   # F-03
                st.session_state.bo_result_summary = {
                    "success_count": 0,
                    "fail_count":    0,
                    "skip_count":    skip_count,
                    "log":           [],
                }
                st.session_state.bo_pending = None   # consumed — clear payload
                st.rerun()

            # ── PHASE B / C: Work loop + finalisation (runs N+2 … M) ─────
            elif bo_running and _queue is not None:

                if st.session_state.get("bo_cancel_requested") or not _queue:
                    # ── PHASE C: Finalise ─────────────────────────────────
                    # Reached when:  (a) user clicked Cancel, or
                    #                (b) the queue has been fully processed.
                    cancelled = bool(st.session_state.get("bo_cancel_requested"))
                    summary   = st.session_state.bo_result_summary or {}
                    job_id    = st.session_state.get("bo_job_id")

                    # F-03 — cancellation acknowledgment. Reuses the existing
                    # cancel flag; no new cancel workflow. The in-flight unit
                    # always finishes naturally (see Cancel button comment
                    # above), so this message reflects that the batch is now
                    # wrapping up rather than starting another unit.
                    if cancelled:
                        st.info("⏳ Stopping after current generation… finalizing batch.")

                    # BT-16 fix: save_story()'s DB commit (inside
                    # generate_next_batch_unit(), called from Phase B)
                    # and this page's bo_result_summary["success_count"]
                    # increment are two separate, non-atomic steps —
                    # the increment only happens *after*
                    # generate_next_batch_unit() returns. If the script
                    # run executing a unit is superseded/interrupted
                    # between those two steps (e.g. a Cancel click
                    # racing a still-running Phase B unit), the story
                    # is already durably saved but bo_result_summary
                    # never advances, so Generate tab / Jobs tab
                    # under-report relative to Repository — the actual
                    # source of truth per the product constitution
                    # ("session state exists only for UI; every
                    # completed operation must eventually exist inside
                    # SQLite"). Reconciling against the persisted count
                    # for this batch_job_id closes that gap without
                    # touching the generation workflow, Phase B's unit
                    # loop, or the cancel-check timing itself.
                    _persisted_count = count_stories_for_generate_job(job_id) if job_id else 0

                    sc  = max(summary.get("success_count", 0), _persisted_count)
                    fc  = summary.get("fail_count",    0)
                    skc = summary.get("skip_count",    0)
                    log = summary.get("log",           [])

                    skip_note   = f", {skc} skipped" if skc else ""
                    cancel_note = ", cancelled"       if cancelled else ""

                    if cancelled:
                        final_status = "partial" if sc > 0 else "failed"
                    elif fc == 0:
                        final_status = "completed"
                    elif sc > 0:
                        final_status = "partial"
                    else:
                        final_status = "failed"

                    if job_id:
                        update_batch_job(
                            job_id,
                            status      = final_status,
                            summary     = f"{sc} generated, {fc} failed{skip_note}{cancel_note}",
                            detail_log  = "\n".join(log) or None,
                            finished_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        )

                    # Persist result for the banner that stays visible until
                    # the next generation run starts.
                    st.session_state.bo_last_result = {
                        "success_count": sc,
                        "fail_count":    fc,
                        "skip_count":    skc,
                        "cancelled":     cancelled,
                    }

                    # P-16 — snapshot the final progress card state, reusing
                    # values already computed above (sc/fc/skc/cancelled) plus
                    # the participant totals already tracked in session state.
                    # No recalculation from the database, no duplicate counters.
                    _p16_total_participants = st.session_state.get("bo_total_participants", 0)
                    _p16_remaining_pids     = {p["id"] for p, _f in (_queue or [])}
                    _p16_completed_participants = max(
                        _p16_total_participants - len(_p16_remaining_pids), 0
                    )
                    st.session_state.bo_last_progress_summary = {
                        "total_participants":     _p16_total_participants,
                        "completed_participants": _p16_completed_participants,
                        "success":                sc,
                        "failed":                 fc,
                        "skipped":                skc,
                        "cancelled":              cancelled,
                    }

                    # Clear all generation state — unlock the UI.
                    st.session_state.bo_pending_queue    = None
                    st.session_state.bo_job_id           = None
                    st.session_state.bo_done_count       = 0
                    st.session_state.bo_total_units      = 0
                    st.session_state.bo_result_summary   = None
                    st.session_state.bo_status_log       = []
                    st.session_state.bo_running          = False
                    st.session_state.bo_cancel_requested = False
                    st.session_state.bo_pending          = None
                    st.rerun()

                else:
                    # ── PHASE B: One unit of work per rerun ───────────────
                    participant, fmt = _queue[0]
                    remaining        = _queue[1:]
                    spec             = STORY_FORMATS.get(fmt, {})

                    done  = st.session_state.bo_done_count
                    # F-03: denominator is the processable-unit count (queue
                    # length), not total_units — total_units includes
                    # skip_existing units that never entered the queue, which
                    # previously made the bar stall below 100%.
                    total = st.session_state.get("bo_processable_units") or (st.session_state.bo_total_units or 1)
                    pct   = int((done / total) * 100) if total else 100

                    # Progress display — re-rendered fresh each rerun
                    st.progress(pct)

                    # F-03 — live counters row (reuses existing bo_result_summary
                    # state; no new counters introduced) + participant-level
                    # rollup (derived from the existing queue tuples — no
                    # changes to build_batch_queue()/batch_service.py).
                    _summary_live       = st.session_state.bo_result_summary or {}
                    _total_participants = st.session_state.get("bo_total_participants", 0)
                    _remaining_pids     = {p["id"] for p, _f in _queue}
                    _completed_pcount   = max(_total_participants - len(_remaining_pids), 0)

                    lc1, lc2, lc3, lc4 = st.columns(4)
                    lc1.markdown(
                        _stat_chip("Participants", f"{_completed_pcount} / {_total_participants}", c["accent"]),
                        unsafe_allow_html=True,
                    )
                    lc2.markdown(
                        _stat_chip("✓ Success", _summary_live.get("success_count", 0), c["green"]),
                        unsafe_allow_html=True,
                    )
                    lc3.markdown(
                        _stat_chip("✗ Failed", _summary_live.get("fail_count", 0), c["red"]),
                        unsafe_allow_html=True,
                    )
                    lc4.markdown(
                        _stat_chip("↷ Skipped", _summary_live.get("skip_count", 0), c["amber"]),
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div style="margin-top:.6rem;"></div>', unsafe_allow_html=True)

                    current_line = (
                        f'⏳ <strong>{participant["name"]}</strong> — '
                        f'{spec.get("label", fmt)}&nbsp;({done + 1}/{total})…'
                    )
                    recent_log = (st.session_state.get("bo_status_log") or [])[-6:]
                    st.markdown(
                        '<div class="sf-generation-status">'
                        + "<br>".join(recent_log + [current_line])
                        + '</div>',
                        unsafe_allow_html=True,
                    )

                    # Cancel button.
                    # on_click fires at the TOP of the NEXT rerun, after the
                    # current Gemini call finishes naturally — the in-flight
                    # HTTP request is never killed.  Consistent with F-01.
                    def _request_bo_cancel():
                        st.session_state.bo_cancel_requested = True

                    st.button(
                        "⛔ Cancel Batch",
                        key="bo_cancel_btn",
                        on_click=_request_bo_cancel,
                    )

                    # ── Service call — pure, no Streamlit ─────────────────
                    result = generate_next_batch_unit(
                        job_id           = st.session_state.bo_job_id,
                        participant      = participant,
                        fmt              = fmt,
                        gen_mode         = st.session_state.bo_active_gen_mode,
                        existing_formats = set(),   # pre-filtered in Phase A
                    )

                    # Update running totals in session state
                    summary = st.session_state.bo_result_summary
                    if result["status"] == "success":
                        summary["success_count"] += 1
                        icon = "✅"
                    elif result["status"] == "skipped":
                        summary["skip_count"] = summary.get("skip_count", 0) + 1
                        icon = "⏭"
                    else:
                        summary["fail_count"] += 1
                        summary["log"].append(result.get("message", ""))
                        icon = "⚠️"

                    done_now = done + 1
                    st.session_state.bo_done_count   = done_now
                    st.session_state.bo_status_log   = (
                        (st.session_state.get("bo_status_log") or [])
                        + [f'{icon} {participant["name"]} — {spec.get("label", fmt)}']
                    )

                    # Persist incremental progress to the batch_jobs row so
                    # the Jobs tab shows live counts during the run.
                    update_batch_job(
                        st.session_state.bo_job_id,
                        processed_items = done_now,
                        success_count   = summary["success_count"],
                        fail_count      = summary["fail_count"],
                    )

                    st.session_state.bo_pending_queue = remaining

                    # Pace calls; skip delay on the very last unit.
                    if remaining:
                        time.sleep(settings.GEMINI_SEQUENTIAL_DELAY)
                    st.rerun()

            # ── P-16 — Persisted final progress card ────────────────────
            # Shown once a run has finished (normally or via cancel) and
            # persists until the next generation starts (bo_last_progress_summary
            # is cleared when run_clicked fires). Reuses the snapshot taken at
            # the moment Phase C finalised — no recomputation, no DB reads.
            _bo_p16 = st.session_state.get("bo_last_progress_summary")
            if _bo_p16 and not bo_running:
                _p16_total_p = _bo_p16["total_participants"]
                _p16_done_p  = _bo_p16["completed_participants"]
                _p16_pct     = int((_p16_done_p / _p16_total_p) * 100) if _p16_total_p else 100
                _p16_cancelled = _bo_p16["cancelled"]

                _p16_title = "⚠ Generation Cancelled" if _p16_cancelled else "✅ Generation Complete"
                _p16_bar_color = c["amber"] if _p16_cancelled else c["green"]

                _section_label("Generation Progress")
                st.markdown(
                    f'<div class="sf-card" style="margin-bottom:1rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'margin-bottom:.5rem;">'
                    f'<span style="font-size:.9rem;font-weight:600;color:{c["text_primary"]};">'
                    f'{_p16_title}</span>'
                    f'<span style="font-size:.78rem;color:{c["text_muted"]};'
                    f'font-family:\'DM Mono\',monospace;">{_p16_done_p} / {_p16_total_p} Participants</span>'
                    f'</div>'
                    + _progress_bar_html(_p16_pct, _p16_bar_color) +
                    f'<div style="display:flex;gap:1.5rem;flex-wrap:wrap;font-size:.8rem;margin-top:.75rem;">'
                    f'<span style="color:{c["green"]};">✓ Success&nbsp;:&nbsp;{_bo_p16["success"]}</span>'
                    f'<span style="color:{c["red"]};">✗ Failed&nbsp;:&nbsp;{_bo_p16["failed"]}</span>'
                    f'<span style="color:{c["amber"]};">↻ Skipped&nbsp;:&nbsp;{_bo_p16["skipped"]}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Result banner (persists until the next generation starts) ──
            _last_result = st.session_state.get("bo_last_result")
            if _last_result and not bo_running:
                sc  = _last_result["success_count"]
                fc  = _last_result["fail_count"]
                skc = _last_result["skip_count"]
                cld = _last_result["cancelled"]
                skip_note = f", {skc} skipped" if skc else ""

                if cld:
                    st.warning(
                        f"⚠ Batch cancelled — {sc} generated, "
                        f"{fc} failed{skip_note}. "
                        f"See the Jobs tab for the full log."
                    )
                elif fc == 0:
                    st.success(
                        f"✅ Generated {sc} "
                        f"{'story' if sc == 1 else 'stories'} "
                        f"successfully{skip_note}."
                    )
                else:
                    st.warning(
                        f"⚠ {sc} succeeded, {fc} failed{skip_note}. "
                        f"See the Jobs tab for the full log."
                    )

            # ══════════════════════════════════════════════════════════
            # BT-08 — PERMANENT EDITORIAL INBOX
            # ──────────────────────────────────────────────────────────
            # Always rendered (not gated on a recent run). Reads all
            # batch-originated drafts directly from the DB via
            # batch_job_id IS NOT NULL, so it survives page reloads,
            # new generation runs, and server restarts.
            #
            # Workspace drafts (batch_job_id = NULL) NEVER appear here.
            # Repository is the only place both origins coexist.
            # ══════════════════════════════════════════════════════════
            st.markdown(
                f'<hr style="border-color:{c["border"]};margin:2rem 0 1.25rem 0;">',
                unsafe_allow_html=True,
            )
            _section_label("Editorial Inbox — Batch Drafts")

            _inbox_all = get_batch_draft_stories()

            if not _inbox_all:
                st.markdown(
                    f'<div style="text-align:center;padding:2rem;'
                    f'border:1.5px dashed {c["border"]};border-radius:12px;'
                    f'color:{c["text_muted"]};font-size:.875rem;">'
                    f'No batch drafts pending review.<br>'
                    f'<span style="font-size:.8rem;">Generate stories above — '
                    f'they will appear here automatically.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                # ── Participant filter ─────────────────────────────────
                _inbox_p_counts = {}
                _inbox_p_names  = {}
                for _s in _inbox_all:
                    _pid = _s.get("participant_id")
                    _inbox_p_counts[_pid] = _inbox_p_counts.get(_pid, 0) + 1
                    _inbox_p_names[_pid]  = _s.get("participant_name", "—")

                _inbox_filter_opts = {"all": f"All Batch Drafts ({len(_inbox_all)})"}
                for _pid in sorted(_inbox_p_names, key=lambda k: _inbox_p_names[k]):
                    _inbox_filter_opts[str(_pid)] = (
                        f"{_inbox_p_names[_pid]} ({_inbox_p_counts[_pid]})"
                    )

                # BT-18 (part 2): st.selectbox's CLOSED-control label can lag
                # behind its OPTIONS popup when the selected "value" itself
                # doesn't change across reruns but the label text for that
                # value does (here: "all" stays "all", but its formatted
                # label "All Batch Drafts (N)" changes as drafts are
                # generated). Streamlit/BaseWeb only reliably re-renders the
                # visible closed-box text when the widget's key changes —
                # the same class of staleness already worked around
                # elsewhere in Workspace via ws_gen_counter-suffixed keys.
                # Keying this selectbox off the current inbox contents
                # forces a fresh widget instance whenever the dataset
                # changes, so the closed label is always freshly computed
                # instead of showing a value cached from a previous render.
                _inbox_ids_sig = ",".join(
                    str(_s["id"]) for _s in sorted(_inbox_all, key=lambda s: s["id"])
                )
                _inbox_key = f"bo_inbox_filter_{hash(_inbox_ids_sig)}"

                # Preserve the user's chosen filter across the key change —
                # re-keying alone would silently reset the selection back to
                # "All Batch Drafts" every time a draft is added or removed.
                _prev_inbox_sel = st.session_state.get("bo_inbox_filter_value", "all")
                _inbox_default_index = (
                    list(_inbox_filter_opts.keys()).index(_prev_inbox_sel)
                    if _prev_inbox_sel in _inbox_filter_opts else 0
                )

                _inbox_sel = st.selectbox(
                    "Filter by participant",
                    options=list(_inbox_filter_opts.keys()),
                    index=_inbox_default_index,
                    format_func=lambda k: _inbox_filter_opts[k],
                    label_visibility="collapsed",
                    key=_inbox_key,
                )
                st.session_state["bo_inbox_filter_value"] = _inbox_sel

                # BT-18: Resolve filtered story list by filtering the SAME
                # _inbox_all result fetched above — never a second DB query.
                # Before this fix, the "specific participant" branch called
                # get_batch_draft_stories(participant_id=...) again, which
                # opened a brand-new connection and ran a fresh SELECT. That
                # gave the filter labels/counts (built from _inbox_all) and
                # the rendered list (built from this second, independent
                # read) two different sources of truth for what should be
                # one dataset — the exact window where, especially amid the
                # rapid reruns right after batch generation, the two reads
                # could observe slightly different states and disagree.
                # Filtering in-memory removes that second read entirely, so
                # filter options, counts, and the rendered list are now
                # structurally guaranteed to match on every render.
                if _inbox_sel == "all":
                    _inbox_stories = _inbox_all
                else:
                    _inbox_stories = [
                        _s for _s in _inbox_all
                        if str(_s.get("participant_id")) == _inbox_sel
                    ]

                _inbox_all_ids = [_s["id"] for _s in _inbox_stories]

                st.markdown(
                    f'<div style="font-size:.78rem;color:{c["text_muted"]};'
                    f'margin:.4rem 0 .75rem 0;">'
                    f'{len(_inbox_stories)} draft{"s" if len(_inbox_stories) != 1 else ""}'
                    f' pending review</div>',
                    unsafe_allow_html=True,
                )

                # ── Select all ─────────────────────────────────────────
                def _apply_inbox_select_all():
                    _checked = bool(st.session_state.get("bo_inbox_select_all", False))
                    for _sid in _inbox_all_ids:
                        st.session_state[f"bo_inbox_card_{_sid}"] = _checked

                st.checkbox(
                    "Select all",
                    key="bo_inbox_select_all",
                    on_change=_apply_inbox_select_all,
                )

                # ── Draft cards (BT-05 design) ─────────────────────────
                for _s in _inbox_stories:
                    _sid     = _s["id"]
                    _fmt     = _s.get("format", "")
                    _spec    = STORY_FORMATS.get(_fmt, {})
                    _icon    = _spec.get("icon", "\u2726")
                    _lbl     = _spec.get("label", _fmt)
                    _wc      = _s.get("word_count", 0) or 0
                    _name    = _s.get("participant_name", "\u2014")
                    _content = (_s.get("content") or "").strip()
                    _preview = _content[:140] + ("\u2026" if len(_content) > 140 else "")

                    with st.container(border=True):
                        # Metadata + preview — pure HTML, zero widgets on this row
                        st.markdown(
                            f'<div style="display:flex;align-items:center;'
                            f'gap:.6rem;flex-wrap:wrap;margin-bottom:.4rem;">'
                            f'<span style="font-size:.88rem;font-weight:700;'
                            f'color:{c["text_primary"]};">{_name}</span>'
                            f'<span style="font-size:.75rem;color:{c["text_secondary"]};">'
                            f'{_icon}&nbsp;{_lbl}</span>'
                            f'<span style="font-family:\'DM Mono\',monospace;'
                            f'font-size:.72rem;color:{c["text_muted"]};">'
                            f'{_wc}\u00a0words</span>'
                            f'<span style="display:inline-flex;align-items:center;'
                            f'padding:.1rem .45rem;border-radius:20px;'
                            f'background:{c["surface_alt"]};color:{c["text_muted"]};'
                            f'font-size:.68rem;font-weight:600;">Draft</span>'
                            f'</div>'
                            f'<div style="font-size:.8rem;color:{c["text_muted"]};'
                            f'font-style:italic;line-height:1.5;margin-bottom:.4rem;">'
                            f'\u201c{_preview}\u201d'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        # Widget row — st.columns required (buttons present)
                        _ic1, _ic2 = st.columns([2, 3])
                        with _ic1:
                            if st.button(
                                "\U0001f441 View in Repository",
                                key=f"bo_inbox_view_{_sid}",
                                use_container_width=True,
                            ):
                                st.session_state["repo_open_story_id"] = _sid
                                st.switch_page("pages/4_Repository.py")
                        with _ic2:
                            st.checkbox(
                                "Select for Review",
                                key=f"bo_inbox_card_{_sid}",
                            )

                # ── Submit bar ─────────────────────────────────────────
                _inbox_sel_ids = [
                    _s["id"] for _s in _inbox_stories
                    if st.session_state.get(f"bo_inbox_card_{_s['id']}", False)
                ]

                _isub1, _igap = st.columns([2, 5])
                with _isub1:
                    if st.button(
                        f"📋 Submit {len(_inbox_sel_ids)} to Review"
                        if _inbox_sel_ids else "📋 Submit to Review",
                        use_container_width=True,
                        disabled=not _inbox_sel_ids,
                        key="bo_inbox_submit_btn",
                    ):
                        _n = bulk_update_story_status(
                            _inbox_sel_ids, "in_review", reviewer="editor"
                        )
                        st.success(f"Submitted {_n} story/stories to Review Queue.")
                        st.rerun()


# ╔══════════════════════════════════════════════════════════════════════
# TAB 3 — JOBS / PROGRESS DASHBOARD
# ╚══════════════════════════════════════════════════════════════════════

with tab_jobs:
    rc1, rc2 = st.columns([5, 2])
    with rc2:
        if st.button("↻ Refresh", use_container_width=True, key="bo_jobs_refresh"):
            st.rerun()

    jobs = list_batch_jobs(limit=25)

    if not jobs:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">'
            f'No batch jobs yet. Imports and bulk generations will show up here.</div>',
            unsafe_allow_html=True,
        )
    else:
        for job in jobs:
            total = job.get("total_items") or 0
            processed = job.get("processed_items") or 0
            pct = int((processed / total) * 100) if total else 0
            status = job.get("status", "pending")
            fg, _ = _JOB_STATUS_CFG.get(status, (c["text_muted"], c["surface_alt"]))

            job_icon = "📥" if job["job_type"] == "import" else "⚡"
            job_label = "Import" if job["job_type"] == "import" else "Bulk Generate"

            with st.container(border=True):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div style="font-size:.88rem;font-weight:600;color:{c["text_primary"]};">'
                    f'{job_icon} {job_label} &nbsp;·&nbsp; Job #{job["id"]}</div>'
                    + _job_status_badge(status) +
                    f'</div>'
                    f'<div style="font-size:.78rem;color:{c["text_muted"]};margin-top:.4rem;">'
                    f'{job.get("summary") or f"{processed} / {total} processed"} '
                    f'&nbsp;·&nbsp; started {job.get("started_at", "—")}'
                    + (f' &nbsp;·&nbsp; finished {job["finished_at"]}' if job.get("finished_at") else "")
                    + f'</div>'
                    + _progress_bar_html(pct, fg),
                    unsafe_allow_html=True,
                )

                sc1, sc2, sc3 = st.columns(3)
                sc1.markdown(
                    f'<div style="font-size:.72rem;color:{c["green"]};margin-top:.5rem;">'
                    f'✓ {job.get("success_count", 0)} succeeded</div>',
                    unsafe_allow_html=True,
                )
                sc2.markdown(
                    f'<div style="font-size:.72rem;color:{c["red"]};margin-top:.5rem;">'
                    f'✗ {job.get("fail_count", 0)} failed</div>',
                    unsafe_allow_html=True,
                )
                sc3.markdown(
                    f'<div style="font-size:.72rem;color:{c["text_muted"]};margin-top:.5rem;">'
                    f'{pct}% complete</div>',
                    unsafe_allow_html=True,
                )

                if job.get("detail_log"):
                    with st.expander("View log", expanded=False):
                        st.markdown(
                            f'<div style="font-size:.78rem;color:{c["text_secondary"]};'
                            f'white-space:pre-wrap;line-height:1.6;">{job["detail_log"]}</div>',
                            unsafe_allow_html=True,
                        )


# ╔══════════════════════════════════════════════════════════════════════
# TAB 4 — BATCH ANALYTICS
# ╚══════════════════════════════════════════════════════════════════════

with tab_analytics:
    participants = get_all_participants()
    stories = get_all_stories()

    if not participants:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">'
            f'No data yet. Import participants and generate stories to see analytics here.</div>',
            unsafe_allow_html=True,
        )
    else:
        _section_label("Overview")
        oc1, oc2, oc3, oc4 = st.columns(4)
        oc1.markdown(_stat_chip("Participants", len(participants)), unsafe_allow_html=True)
        oc2.markdown(_stat_chip("Stories", len(stories)), unsafe_allow_html=True)
        gen_jobs = [j for j in list_batch_jobs(limit=100) if j["job_type"] == "generate"]
        total_gen_attempts = sum((j.get("success_count") or 0) + (j.get("fail_count") or 0) for j in gen_jobs)
        total_gen_success = sum(j.get("success_count") or 0 for j in gen_jobs)
        success_rate = round((total_gen_success / total_gen_attempts) * 100) if total_gen_attempts else 0
        oc3.markdown(
            _stat_chip("Gen. Success Rate", f"{success_rate}%",
                       c["green"] if success_rate >= 80 else c["amber"]),
            unsafe_allow_html=True,
        )
        avg_wc = round(sum(s.get("word_count", 0) or 0 for s in stories) / len(stories)) if stories else 0
        oc4.markdown(_stat_chip("Avg. Word Count", avg_wc), unsafe_allow_html=True)

        # ── By program ──────────────────────────────────────────────
        _section_label("Stories by Program")
        program_counts = {}
        for p in participants:
            prog = p.get("program") or "Unassigned"
            program_counts.setdefault(prog, {"participants": 0, "stories": 0})
            program_counts[prog]["participants"] += 1
        for s in stories:
            prog = s.get("program") or "Unassigned"
            program_counts.setdefault(prog, {"participants": 0, "stories": 0})
            program_counts[prog]["stories"] += 1

        max_stories = max((v["stories"] for v in program_counts.values()), default=1) or 1
        for prog, v in sorted(program_counts.items(), key=lambda kv: -kv[1]["stories"]):
            pct = int((v["stories"] / max_stories) * 100)
            st.markdown(
                f'<div style="margin-bottom:.6rem;">'
                f'<div style="display:flex;justify-content:space-between;font-size:.8rem;">'
                f'<span style="color:{c["text_secondary"]};">{prog}</span>'
                f'<span style="color:{c["text_muted"]};">'
                f'{v["participants"]} participant(s) &nbsp;·&nbsp; {v["stories"]} stor{"y" if v["stories"]==1 else "ies"}</span>'
                f'</div>'
                + _progress_bar_html(pct, c["accent"]) +
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── By format ───────────────────────────────────────────────
        _section_label("Stories by Format")
        for fmt_key, spec in STORY_FORMATS.items():
            fmt_stories = [s for s in stories if s.get("format") == fmt_key]
            if not fmt_stories:
                continue
            wmin, wmax = spec["word_range"]
            in_range = sum(1 for s in fmt_stories if wmin <= (s.get("word_count") or 0) <= wmax)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:.65rem;'
                f'padding:.35rem 0;border-bottom:1px solid {c["border"]};">'
                + format_badge(fmt_key)
                + f'<span style="font-size:.8rem;color:{c["text_secondary"]};">'
                  f'{len(fmt_stories)} stories</span>'
                + f'<span style="font-size:.72rem;color:{c["text_muted"]};margin-left:auto;">'
                  f'{in_range}/{len(fmt_stories)} within target word range</span>'
                + '</div>',
                unsafe_allow_html=True,
            )

        # ── By status ───────────────────────────────────────────────
        _section_label("Status Breakdown")
        status_order = ["draft", "in_review", "approved", "published", "rejected"]
        status_counts = {s: 0 for s in status_order}
        for s in stories:
            key = s.get("status", "draft")
            if key in status_counts:
                status_counts[key] += 1
        sb_cols = st.columns(len(status_order))
        for col, status in zip(sb_cols, status_order):
            col.markdown(
                _stat_chip(status.replace("_", " ").title(), status_counts[status]),
                unsafe_allow_html=True,
            )