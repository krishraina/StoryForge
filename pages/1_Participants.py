"""
StoryForge — Participants V2
────────────────────────────
Tab 1 — All Participants
  • Search / filter bar (name, program, domain)
  • Story status breakdown per row (mini-pills)
  • Expandable profile drawer per participant:
      - Full field details (background, achievements, challenges, outcomes)
      - Story list with format + status badges
      - "Open in Workspace" button
      - Delete with 2-step confirmation

Tab 2 — Add / Edit
  • Edit-mode selector (pre-fills form for existing participant)
  • LinkedIn Profile URL field (stored reference, no scraping)
  • Program "Other" selector lives OUTSIDE st.form() (rerun-safe)
  • enter_to_submit=False prevents accidental submission
"""

import streamlit as st

from components.theme    import page_config, apply_theme, COLORS
from components.badges   import status_badge, format_badge, participant_options
from services.db_service import (
    get_all_participants,
    get_participant,
    upsert_participant,
    delete_participant,
    get_stories_for_participant,
    email_exists,
)
from core.constants import PROGRAMS, DOMAINS, CONSENT_LEVELS, STORY_FORMATS
from core.database  import init_db

# ── Boot ──────────────────────────────────────────────────────────────
init_db()
page_config("Participants")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()
c = COLORS

# ── Session state ─────────────────────────────────────────────────────
if "confirm_delete_pid" not in st.session_state:
    st.session_state.confirm_delete_pid = None
if "ws_selected_pid" not in st.session_state:
    st.session_state.ws_selected_pid = None


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS  (all defined before any module-level call / widget)
# ══════════════════════════════════════════════════════════════════════

def _story_status_counts(stories: list) -> dict:
    """Return {status: count} for a participant story list."""
    counts = {"draft": 0, "in_review": 0, "approved": 0,
              "published": 0, "rejected": 0}
    for s in stories:
        key = s.get("status", "draft")
        if key in counts:
            counts[key] += 1
    return counts


def _mini_pill(status: str, count: int) -> str:
    cfg = {
        "draft":     (c["text_muted"],  c["surface_alt"], "draft"),
        "in_review": (c["amber"],       c["amber_soft"],  "review"),
        "approved":  (c["green"],       c["green_soft"],  "approved"),
        "published": (c["purple"],      c["purple_soft"], "published"),
        "rejected":  (c["red"],         c["red_soft"],    "rejected"),
    }
    fg, bg, label = cfg.get(status, (c["text_muted"], c["surface_alt"], status))
    return (
        f'<span style="display:inline-flex;align-items:center;'
        f'padding:.1rem .45rem;border-radius:12px;background:{bg};'
        f'color:{fg};font-size:.68rem;font-weight:600;margin-right:.3rem;">'
        f'{count} {label}</span>'
    )


def _status_breakdown_html(counts: dict) -> str:
    total = sum(counts.values())
    if total == 0:
        return f'<span style="font-size:.75rem;color:{c["text_muted"]};">no stories</span>'
    return "".join(_mini_pill(s, n) for s, n in counts.items() if n > 0)


def _consent_color(level: str) -> str:
    return {
        "full":       c["green"],
        "anonymized": c["amber"],
        "internal":   c["text_muted"],
        "none":       c["red"],
    }.get(level, c["text_muted"])


def _field_block(label: str, value: str) -> str:
    val = value.strip() if value and value.strip() else "\u2014"
    return (
        f'<div style="margin-bottom:.65rem;">'
        f'<div style="font-size:.67rem;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:.07em;color:{c["text_muted"]};margin-bottom:.15rem;">{label}</div>'
        f'<div style="font-size:.83rem;color:{c["text_secondary"]};'
        f'line-height:1.6;white-space:pre-wrap;">{val}</div>'
        f'</div>'
    )


# ══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
         margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div>
            <div class="sf-page-title">Participants</div>
            <div class="sf-page-subtitle">Manage participant profiles, consent levels, and story data</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════

tab_list, tab_add = st.tabs(["All Participants", "Add / Edit"])


# ╔══════════════════════════════════════════════════════════════════════
# TAB 1 — ALL PARTICIPANTS
# ╚══════════════════════════════════════════════════════════════════════

with tab_list:
    participants = get_all_participants()

    if not participants:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">'
            f'No participants yet. Use the <strong>Add / Edit</strong> tab to add one.'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        # ── Search / filter bar — one toolbar, not three separate fields ─
        with st.container(border=True):
            sf1, sf2, sf3 = st.columns([3, 2, 2], gap="medium")
            with sf1:
                search_q = st.text_input(
                    "Search",
                    placeholder="Search by name, program, or domain…",
                    label_visibility="collapsed",
                    key="ptab_search",
                )
            with sf2:
                prog_set = sorted({p.get("program") or "" for p in participants} - {""})
                prog_filter = st.selectbox(
                    "Program filter",
                    ["All programs"] + prog_set,
                    label_visibility="collapsed",
                    key="ptab_prog_filter",
                )
            with sf3:
                consent_filter = st.selectbox(
                    "Consent filter",
                    ["All consent levels"] + list(CONSENT_LEVELS.keys()),
                    format_func=lambda k: (
                        "All consent levels" if k == "All consent levels"
                        else CONSENT_LEVELS[k].split("\u2014")[0].split("—")[0].strip()
                    ),
                    label_visibility="collapsed",
                    key="ptab_consent_filter",
                )

        # Apply filters
        filtered = participants
        if search_q:
            q = search_q.lower()
            filtered = [
                p for p in filtered
                if q in (p.get("name") or "").lower()
                or q in (p.get("program") or "").lower()
                or q in (p.get("domain") or "").lower()
            ]
        if prog_filter != "All programs":
            filtered = [p for p in filtered if p.get("program") == prog_filter]
        if consent_filter != "All consent levels":
            filtered = [p for p in filtered if p.get("consent_level") == consent_filter]

        st.markdown(
            f'<div style="font-size:.78rem;color:{c["text_muted"]};margin:.9rem 0 .6rem 0;">'
            f'{len(filtered)} of {len(participants)} participants</div>',
            unsafe_allow_html=True,
        )

        if not filtered:
            st.markdown(
                f'<div style="text-align:center;padding:2rem;color:{c["text_muted"]};">'
                f'No participants match your filters.</div>',
                unsafe_allow_html=True,
            )
        else:
            # Header columns (st.columns — keeps alignment consistent)
            hc1, hc2, hc3, hc4, hc5 = st.columns([3, 2, 2, 2, 3])
            for col, label in zip(
                [hc1, hc2, hc3, hc4, hc5],
                ["Name", "Program", "Domain", "Consent", "Stories"]
            ):
                col.markdown(
                    f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.07em;color:{c["text_secondary"]};padding:.35rem 0;">{label}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                '<hr style="border-color:rgba(255,255,255,0.09);margin:.15rem 0 .35rem 0;">',
                unsafe_allow_html=True,
            )

            # ── Participant rows with expander drawers ────────────────
            for p in filtered:
                pid       = p["id"]
                stories   = get_stories_for_participant(pid)
                counts    = _story_status_counts(stories)
                total_cnt = sum(counts.values())
                c_level   = p.get("consent_level", "none")
                c_color   = _consent_color(c_level)
                c_label   = CONSENT_LEVELS.get(c_level, c_level)

                # Expander label — plain text (no HTML allowed in label)
                exp_label = (
                    f"{p['name']}  \u00b7  "
                    f"{p.get('program') or 'No program'}  \u00b7  "
                    f"{total_cnt} {'story' if total_cnt == 1 else 'stories'}"
                )

                with st.expander(exp_label, expanded=False):

                    # Top metadata strip (display-only HTML — no widgets here)
                    linkedin_url = (p.get("linkedin_url") or "").strip()
                    linkedin_chip = (
                        f'<div><div style="font-size:.67rem;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:{c["text_muted"]};">LinkedIn</div>'
                        f'<div style="font-size:.83rem;margin-top:.1rem;">'
                        f'<a href="{linkedin_url}" target="_blank" '
                        f'style="color:{c["accent"]};text-decoration:none;">View Profile</a>'
                        f'</div></div>'
                        if linkedin_url else ""
                    )

                    st.markdown(
                        f'<div style="display:flex;gap:2rem;flex-wrap:wrap;'
                        f'margin-bottom:1rem;padding-bottom:.85rem;'
                        f'border-bottom:1px solid {c["border"]};">'
                        f'<div><div style="font-size:.67rem;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:{c["text_muted"]};">Email</div>'
                        f'<div style="font-size:.83rem;color:{c["text_secondary"]};'
                        f'margin-top:.1rem;">{p.get("email") or "&mdash;"}</div></div>'
                        f'<div><div style="font-size:.67rem;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:{c["text_muted"]};">Domain</div>'
                        f'<div style="font-size:.83rem;color:{c["text_secondary"]};'
                        f'margin-top:.1rem;">{p.get("domain") or "&mdash;"}</div></div>'
                        f'<div><div style="font-size:.67rem;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:{c["text_muted"]};">Consent</div>'
                        f'<div style="font-size:.83rem;color:{c_color};font-weight:600;'
                        f'margin-top:.1rem;">{c_label.split("&mdash;")[0].split("—")[0].strip()}</div></div>'
                        f'{linkedin_chip}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Detail fields — 2 columns
                    dr1, dr2 = st.columns(2)
                    with dr1:
                        st.markdown(
                            _field_block("Background", p.get("background") or "")
                            + _field_block("Challenges Overcome", p.get("challenges") or ""),
                            unsafe_allow_html=True,
                        )
                    with dr2:
                        st.markdown(
                            _field_block("Key Achievements", p.get("achievements") or "")
                            + _field_block("Outcomes & Impact", p.get("outcomes") or ""),
                            unsafe_allow_html=True,
                        )

                    # Stories section label
                    st.markdown(
                        f'<div style="font-size:.7rem;font-weight:600;text-transform:uppercase;'
                        f'letter-spacing:.08em;color:{c["text_muted"]};'
                        f'margin:.85rem 0 .4rem 0;">Stories</div>',
                        unsafe_allow_html=True,
                    )

                    if not stories:
                        st.markdown(
                            f'<div style="font-size:.82rem;color:{c["text_muted"]};'
                            f'font-style:italic;">No stories generated yet.</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        # Status pill summary row
                        st.markdown(_status_breakdown_html(counts), unsafe_allow_html=True)
                        st.markdown('<div style="margin:.5rem 0;"></div>', unsafe_allow_html=True)

                        # Per-story list rows — display only. Individual story
                        # deletion lives in Repository, not here; this page
                        # only manages the participant record as a whole.
                        for s in stories:
                            fmt_spec = STORY_FORMATS.get(s.get("format", ""), {})
                            fmt_icon = fmt_spec.get("icon", "\u2726")
                            fmt_lbl  = fmt_spec.get("label", s.get("format", ""))
                            wc       = s.get("word_count", 0)
                            st.markdown(
                                f'<div style="display:flex;align-items:center;gap:.6rem;'
                                f'padding:.3rem 0;border-bottom:1px solid {c["border"]};">'
                                + status_badge(s.get("status", "draft"))
                                + f'<span style="font-size:.78rem;color:{c["text_secondary"]};">'
                                  f'{fmt_icon} {fmt_lbl}</span>'
                                + f'<span style="font-size:.72rem;color:{c["text_muted"]};'
                                  f'font-family:\'DM Mono\',monospace;margin-left:auto;">'
                                  f'{wc} words</span>'
                                + '</div>',
                                unsafe_allow_html=True,
                            )

                    # Action row — st.columns required (buttons present)
                    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
                    act1, act2, _gap = st.columns([2, 2, 5])

                    with act1:
                        if st.button(
                            "Open in Workspace",
                            key=f"tbl_ws_{pid}",
                            use_container_width=True,
                        ):
                            st.session_state.ws_selected_pid = pid
                            st.switch_page("pages/2_Workspace.py")

                    with act2:
                        if st.session_state.confirm_delete_pid == pid:
                            # Armed: show confirm / cancel
                            st.markdown(
                                f'<div style="font-size:.76rem;color:{c["red"]};'
                                f'font-weight:600;margin-bottom:.3rem;">'
                                f'Delete participant + all {total_cnt} '
                                f'{"story" if total_cnt == 1 else "stories"}? '
                                f'This can\u2019t be undone.</div>',
                                unsafe_allow_html=True,
                            )
                            cfm_y, cfm_n = st.columns(2)
                            with cfm_y:
                                if st.button(
                                    "Yes, delete",
                                    key=f"tbl_del_cfm_yes_{pid}",
                                    use_container_width=True,
                                ):
                                    delete_participant(pid)
                                    st.session_state.confirm_delete_pid = None
                                    st.success("Participant deleted.")
                                    st.rerun()
                            with cfm_n:
                                if st.button(
                                    "Cancel",
                                    key=f"tbl_del_cfm_no_{pid}",
                                    use_container_width=True,
                                ):
                                    st.session_state.confirm_delete_pid = None
                                    st.rerun()
                        else:
                            if st.button(
                                "Delete Participant",
                                key=f"tbl_del_{pid}",
                                use_container_width=True,
                            ):
                                st.session_state.confirm_delete_pid = pid
                                st.rerun()


# ╔══════════════════════════════════════════════════════════════════════
# TAB 2 — ADD / EDIT
# ╚══════════════════════════════════════════════════════════════════════

with tab_add:

    st.markdown('<div class="sf-section-label">Participant Profile</div>', unsafe_allow_html=True)

    # ── Edit-mode selector (OUTSIDE form — needs immediate rerun) ─────
    all_p_for_edit = get_all_participants()
    # FB-03: shared helper builds display labels — unique names pass through,
    # duplicates get a disambiguating suffix.
    edit_options   = {"new": "Add new participant"} | participant_options(all_p_for_edit)

    selected_edit_id = st.selectbox(
        "Choose participant to edit, or add new",
        options=list(edit_options.keys()),
        format_func=lambda k: edit_options[k],
        label_visibility="collapsed",
        key="edt_select",
    )

    if selected_edit_id == "new":
        prefill       = {}
        form_subtitle = "Fill in the details below."
        submit_label  = "Save Participant"
    else:
        prefill       = get_participant(selected_edit_id) or {}
        form_subtitle = f"Editing profile for {prefill.get('name', '')}."
        submit_label  = "Update Participant"

    st.markdown(
        f'<div style="font-size:.8rem;color:{c["text_muted"]};margin-bottom:.75rem;">'
        f'{form_subtitle}</div>',
        unsafe_allow_html=True,
    )

    # ── Program select (OUTSIDE form — "Other" conditional needs rerun) ──
    program_options  = PROGRAMS + ["Other (type below)"]
    prefill_prog     = prefill.get("program") or ""
    prog_default_idx = (
        program_options.index(prefill_prog)
        if prefill_prog in program_options else 0
    )
    program_choice = st.selectbox(
        "Program",
        program_options,
        index=prog_default_idx,
        key=f"edt_program_choice_{selected_edit_id}",
    )
    if program_choice == "Other (type below)":
        custom_default = (
            "" if selected_edit_id == "new" or prefill_prog in PROGRAMS
            else prefill_prog
        )
        program = st.text_input(
            "Enter custom program name",
            value=custom_default,
            key=f"edt_program_custom_{selected_edit_id}",
        )
    else:
        program = program_choice

    # ── Form (only widgets that don't need live conditional rerun) ─────
    with st.form(f"participant_form_{selected_edit_id}", enter_to_submit=False, clear_on_submit=False):

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(
                "Full Name *",
                value=prefill.get("name", ""),
                key=f"edt_name_{selected_edit_id}",
            )
            email = st.text_input(
                "Email",
                value=prefill.get("email") or "",
                key=f"edt_email_{selected_edit_id}",
            )
            linkedin_url = st.text_input(
                "LinkedIn Profile URL (optional)",
                value=prefill.get("linkedin_url") or "",
                placeholder="https://linkedin.com/in/username",
                key=f"edt_linkedin_{selected_edit_id}",
            )
        with col2:
            domain_list    = [""] + DOMAINS
            prefill_domain = prefill.get("domain") or ""
            domain_idx     = (
                domain_list.index(prefill_domain)
                if prefill_domain in domain_list else 0
            )
            domain = st.selectbox(
                "Domain",
                domain_list,
                index=domain_idx,
                key=f"edt_domain_{selected_edit_id}",
            )
            consent_keys    = list(CONSENT_LEVELS.keys())
            prefill_consent = prefill.get("consent_level", "full")
            consent_idx     = (
                consent_keys.index(prefill_consent)
                if prefill_consent in consent_keys else 0
            )
            consent = st.selectbox(
                "Consent Level",
                options=consent_keys,
                index=consent_idx,
                format_func=lambda k: CONSENT_LEVELS[k],
                key=f"edt_consent_{selected_edit_id}",
            )

        st.markdown('<div style="margin-top:.75rem;"></div>', unsafe_allow_html=True)

        background = st.text_area(
            "Background",
            value=prefill.get("background") or "",
            height=90,
            placeholder="Brief bio, prior context...",
            key=f"edt_background_{selected_edit_id}",
        )
        achievements = st.text_area(
            "Key Achievements",
            value=prefill.get("achievements") or "",
            height=90,
            placeholder="What did they accomplish?",
            key=f"edt_achievements_{selected_edit_id}",
        )
        challenges = st.text_area(
            "Challenges Overcome",
            value=prefill.get("challenges") or "",
            height=90,
            placeholder="Obstacles they navigated...",
            key=f"edt_challenges_{selected_edit_id}",
        )
        outcomes = st.text_area(
            "Outcomes & Impact",
            value=prefill.get("outcomes") or "",
            height=90,
            placeholder="Measurable results, transformation...",
            key=f"edt_outcomes_{selected_edit_id}",
        )

        submitted = st.form_submit_button(submit_label, use_container_width=True)

    # ── Handle submission ─────────────────────────────────────────────
    if submitted:
        _email_val  = email.strip() or None
        _editing_pid = selected_edit_id if selected_edit_id != "new" else None

        if not name.strip():
            st.error("Name is required.")
        elif program_choice == "Other (type below)" and not program.strip():
            st.error("Please enter a custom program name, or choose an existing program.")
        elif _email_val and email_exists(_email_val, exclude_pid=_editing_pid):
            st.error(
                f"The email **{_email_val}** is already registered to another participant. "
                "Please use a different email or leave it blank."
            )
        else:
            payload = {
                "name":          name.strip(),
                "email":         email.strip() or None,
                "program":       (program or "").strip() or None,
                "domain":        domain or None,
                "background":    background.strip(),
                "achievements":  achievements.strip(),
                "challenges":    challenges.strip(),
                "outcomes":      outcomes.strip(),
                "consent_level": consent,
                "linkedin_url":  linkedin_url.strip() or None,
            }
            if selected_edit_id != "new":
                payload["id"] = selected_edit_id

            upsert_participant(payload)

            if selected_edit_id == "new":
                st.success(f"Participant '{name.strip()}' added successfully.")
            else:
                st.success(f"Participant '{name.strip()}' updated successfully.")

            st.rerun()