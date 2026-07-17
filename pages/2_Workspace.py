"""
StoryForge — Workspace  (Phase 6C + FB-04 + F-05 Information Architecture)
────────────────────────────────────
Operational story generation & editorial workspace.

LEFT  — Participant context sidebar only: selector, info card, existing
        stories. Nothing else lives here anymore.
RIGHT — The complete editorial workflow: participant overview → story
        formats → compliance → generate → editor tabs → save/submit.
        One continuous panel that naturally transitions from "context"
        to "configure" to "edit" as the session progresses.

FB-04 — Pending Draft Warning
──────────────────────────────
Guards three existing destructive actions (switching participant, loading
a different existing story, starting a new generation run) so unsaved
editor text is never silently discarded. The dirty-check is 100%
session-state — it compares the live editor text (ws_edited) against
ws_saved_baseline, an in-memory record of the last text known to be
persisted, updated only at the existing Save Draft / Submit for Review /
Load Selected Story points. No database reads are introduced anywhere in
this flow. Confirmation reuses the same inline arm/confirm/cancel pattern
already used by Repository delete and Batch Operations batch-delete.

F-05A / F-05B / F-05C (superseded by the IA revision below, kept for
history) — spacing and empty-state work that stayed in the left panel.

F-05 — Information Architecture Revision
──────────────────────────────────────────────
After shipping F-05A (left-panel cleanup), F-05B (empty-state context
cards) and F-05C (compaction polish), the left panel still kept growing
vertically while the right panel sat empty until Generate was clicked.
Compressing spacing was treating the symptom — the real issue was that
configuration (left) and output (right) were split across the wrong
boundary.

This revision re-splits the page along a cleaner boundary:
  • LEFT is now PURELY participant context — selector, info card,
    existing stories. Nothing else.
  • RIGHT is now the full editorial workflow — Story Overview / Format
    Coverage / Latest Story (or the empty hero state), Story Formats,
    a compact Compliance block (consent + AI disclosure — same two
    checkboxes, same logic, relabeled/regrouped), and Generate Stories,
    all stacked above where the editor tabs appear once stories exist.
    Once tabs exist, those same controls collapse into a closed
    expander above the tabs rather than disappearing — so nothing that
    used to be reachable becomes unreachable.
  • The old hard `st.stop()` consent gate (which lived in the left
    panel and halted the entire script) is now a conditional inside the
    right panel: consent_ok is computed once in the left panel (where
    the participant is fetched) and gates only the right panel's
    workflow section. The check itself — same three consent levels,
    same warning copy — is unchanged.

No workflow, business logic, session-state keys, callbacks, or widget
keys were changed by this revision — only which container each existing
block renders into, and two copy-only tweaks ("choose formats below"
instead of "on the left") to match the new location of the controls.

P-14 / P-15 — Polish Tracker
──────────────────────────────
P-14: _render_discard_confirm() buttons now stack full-width instead of
sitting in a narrow two-column split, so "Discard & Continue" never
wraps mid-word regardless of which panel (narrow left / wide right)
the confirmation is rendered in. No wording or workflow change.

P-15: A new _controls_locked() helper returns True whenever EITHER
ws_generating OR ws_confirm_discard is active — no new session-state
key, just a computed OR of two that already exist. Every disabled=
condition that previously read st.session_state.ws_generating now
reads _controls_locked(), so the moment a discard confirmation is
pending, every other Workspace control (participant selector, format
selector, Generate, Existing Stories dropdown, Load Story, editor,
notes, Save Draft, Submit Review, Save All, Submit All, Regenerate,
Retry) is disabled until the user resolves the confirmation.
"""

import time
import streamlit as st

from components.theme  import page_config, apply_theme, COLORS
from components.badges import (
    status_badge,
    format_badge,
    word_count_indicator,
    participant_options,
    format_options,
)
from core.constants    import STORY_FORMATS, CONSENT_LEVELS, AI_DISCLOSURE
from services.db_service import (
    get_all_participants,
    get_participant,
    get_stories_for_participant,
    save_story,
    update_story_status,
)
from core.config import settings
from services.gemini_service import (
    generate_story,
    is_api_configured,
    count_words,
)

# ── Page setup ───────────────────────────────────────────────────────
page_config("Workspace")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()
c = COLORS

# ── Session state keys ───────────────────────────────────────────────
def _init_state():
    defaults = {
        "ws_selected_pid":    None,
        "ws_generated":       {},   # {fmt: {"content": str, "prompt": str} | {"error": str}}
        "ws_edited":          {},   # {fmt: str}  — in-editor overrides
        "ws_saved_ids":       {},   # {fmt: story_db_id}
        "ws_generating":      False,
        "ws_pending":         None,
        "ws_gen_progress":    [],   # list of status lines
        "ws_formats_sel":     ["linkedin", "narrative"],
        "ws_consent_checked": False,
        "ws_disclosure_ack":  False,
        "ws_load_trigger":    None, # {fmt, story_id, content, prompt} — set by Load button, consumed on rerun
        "ws_gen_counter":     {},   # {fmt: int} — bumped every time fresh content lands in the editor,
                                     # forces the text_area to a new widget key so Streamlit can't
                                     # serve stale cached text for that key
        "ws_inline_pending":  None, # fmt string while a Retry/Regenerate run is queued or in flight
        # F-01 — Cancel Generation
        "ws_cancel_requested": False,  # set True by Cancel button on_click; checked between formats
        "ws_total_fmts":       0,      # total formats in this run (for progress %)
        "ws_skipped_fmts":     [],     # formats not generated because cancel was requested
        # FB-04 — Pending Draft Warning (session-state only, no DB reads)
        "ws_saved_baseline":  {},   # {fmt: last-persisted content str} — dirty-check baseline
        "ws_confirm_discard": None, # {"action": ..., ...} pending destructive action awaiting confirm
        "ws_pending_revert_pid": None,  # BT-14 — pid to restore into ws_pid_select before next selectbox render
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# F-01: pre-resolve cancel request before any panel renders.
# The Cancel button's on_click sets ws_cancel_requested at the start
# of widget processing for the run after the current API call finishes.
# By resolving it HERE — before the left panel draws — ws_generating is
# already False when the participant selector, workflow controls, and
# Generate button are instantiated. The workspace is editable in the
# SAME rerun the cancel fires; no intermediate locked-panel frame occurs.
if st.session_state.get("ws_cancel_requested") and st.session_state.get("ws_generating"):
    _pending_at_cancel = list(st.session_state.get("ws_pending") or [])
    st.session_state.ws_skipped_fmts    = _pending_at_cancel
    st.session_state.ws_pending         = None
    st.session_state.ws_generating      = False
    st.session_state.ws_cancel_requested = False


# ── Helpers ───────────────────────────────────────────────────────────

def _word_range(fmt: str):
    return STORY_FORMATS[fmt]["word_range"]


def _bump_gen_counter(fmt: str):
    """
    Increment the per-format generation counter. The text_area key for
    that format includes this counter, so any time fresh content lands
    (generate, regenerate, retry, or load-to-edit) Streamlit treats it
    as a brand-new widget instead of reusing cached state under the old key.
    """
    st.session_state.ws_gen_counter[fmt] = st.session_state.ws_gen_counter.get(fmt, 0) + 1


def _reset_generation():
    st.session_state.ws_generated        = {}
    st.session_state.ws_edited           = {}
    st.session_state.ws_saved_ids        = {}
    st.session_state.ws_gen_progress     = []
    st.session_state.ws_cancel_requested = False
    st.session_state.ws_skipped_fmts     = []
    st.session_state.ws_saved_baseline   = {}     # FB-04


def _progress_callback(fmt, idx, total, status):
    spec  = STORY_FORMATS.get(fmt, {})
    label = spec.get("label", fmt)
    icon  = spec.get("icon", "✦")

    if status == "generating":
        line = f"⏳  Generating **{label}** ({idx + 1}/{total})…"
    elif status == "success":
        line = f"✅  **{label}** — done"
    else:
        line = f"⚠️  **{label}** — generation issue, continuing…"

    st.session_state.ws_gen_progress.append(line)


def _load_story_into_editor(story: dict):
    """
    Populate session state so the right panel opens this story for editing.
    Called when user clicks 'Load' on an existing story row.
    Sets ws_generated, ws_edited, ws_saved_ids for the story's format,
    then triggers a rerun so the right panel reflects the loaded content.
    """
    fmt     = story["format"]
    content = story.get("content") or ""
    prompt  = story.get("generation_prompt") or ""
    sid     = story["id"]

    st.session_state.ws_generated[fmt] = {"content": content, "prompt": prompt}
    st.session_state.ws_edited[fmt]    = content
    st.session_state.ws_saved_ids[fmt] = sid
    st.session_state.ws_saved_baseline[fmt] = content   # FB-04 — loaded content matches the DB, not dirty
    _bump_gen_counter(fmt)


# ── FB-04 — Pending Draft Warning ───────────────────────────────────────
# Session-state only. No database reads anywhere in this logic. Compares
# the live editor text for each format against ws_saved_baseline — the
# last text known to be persisted (set after Save Draft / Submit for
# Review / Load Selected Story). A format with edited content but no
# baseline entry has never been saved at all, so it counts as unsaved.

def _has_unsaved_changes() -> bool:
    for fmt, edited_text in st.session_state.ws_edited.items():
        edited_text = (edited_text or "").strip()
        if not edited_text:
            continue
        baseline = st.session_state.ws_saved_baseline.get(fmt)
        # No baseline means this format has never been saved.
        if baseline is None or edited_text != baseline.strip():
            return True
    return False


# ── P-15 — Workspace confirmation modal state ──────────────────────────
# Treat ws_confirm_discard exactly like ws_generating when deciding
# whether a control should be disabled. This is a computed helper, not a
# new session-state key — it just OR's two flags that already exist, so
# every existing disabled=st.session_state.ws_generating condition below
# now also locks while a discard confirmation is pending.

def _controls_locked() -> bool:
    return bool(st.session_state.ws_generating) or bool(st.session_state.get("ws_confirm_discard"))


def _render_discard_confirm(message: str, discard_key: str, cancel_key: str):
    """
    Inline confirm/cancel banner — same visual pattern already used for
    Repository delete and Batch Operations batch-delete confirmations.
    Returns "discard", "cancel", or None (no button pressed this render).

    P-14: buttons are stacked full-width rather than split across narrow
    columns, so "Discard & Continue" reads on one line regardless of
    whether this renders in the narrow left panel or the wider right
    panel. Wording and workflow are unchanged.
    """
    st.markdown(
        f'<div style="background:{c["amber_soft"]};border:1px solid {c["amber"]};'
        f'border-left:3px solid {c["amber"]};border-radius:0 8px 8px 0;'
        f'padding:.75rem 1rem;margin-bottom:.75rem;font-size:.85rem;'
        f'color:{c["text_secondary"]};">'
        f'⚠️&nbsp;&nbsp;{message}</div>',
        unsafe_allow_html=True,
    )
    discard = st.button("Discard & Continue", key=discard_key, use_container_width=True)
    cancel  = st.button("Cancel", key=cancel_key, use_container_width=True)
    if discard:
        return "discard"
    if cancel:
        return "cancel"
    return None


# ── F-05 IA — Editorial workflow controls (Story Formats → Compliance →
# Generate Stories) ─────────────────────────────────────────────────────
# Extracted into a single rendering helper so the pre-generation (inline)
# and post-generation (collapsed-expander) call sites share one copy of
# this code instead of duplicating it. Every widget key=, value=, and
# disabled= below is byte-identical to the original left-panel
# implementation — only the call site (and therefore the on-screen
# container) changed. Reads the module-level `consent` / `consent_label`
# set in the LEFT panel below; both already exist by the time this is
# called on every real run.

def _render_generate_controls():
    # ── Story Formats ───────────────────────────────────────────────
    st.markdown('<div class="sf-section-label">Story Formats</div>', unsafe_allow_html=True)

    # FB-03: shared helper replaces the locally duplicated {icon label} dict
    fmt_labels = format_options()
    selected_fmts = st.multiselect(
        "Select formats to generate",
        options=list(fmt_labels.keys()),
        default=st.session_state.ws_formats_sel,
        format_func=lambda k: fmt_labels[k],
        label_visibility="collapsed",
        disabled=_controls_locked(),
    )
    if not st.session_state.ws_generating:
        st.session_state.ws_formats_sel = selected_fmts
    else:
        # Freeze the format list that's actually being generated — the
        # widget is disabled so selected_fmts already equals the frozen
        # list, but we read from session_state explicitly for clarity
        # and so a stray widget interaction can never substitute a
        # different list mid-run.
        selected_fmts = st.session_state.ws_formats_sel

    # ── Compliance (Consent + AI Disclosure, compacted per F-05C/C2) ──
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-label">Compliance</div>', unsafe_allow_html=True)

    icon  = "✓" if consent == "full" else "⚠" if consent == "anonymized" else "🔒"
    css_c = "sf-consent-ok" if consent == "full" else "sf-consent-warn"

    cc1, cc2 = st.columns([1.1, 1.6], gap="small")
    with cc1:
        st.markdown(
            f'<div class="{css_c}" style="margin:0;padding:.45rem .6rem;'
            f'font-size:.78rem;line-height:1.4;">'
            f'{icon}&nbsp;{consent_label}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with cc2:
        consent_confirmed = st.checkbox(
            "I confirm participant consent has been verified",
            value=st.session_state.ws_consent_checked,
            key="consent_chk",
            disabled=_controls_locked(),
        )
    st.session_state.ws_consent_checked = consent_confirmed

    st.markdown('<div style="margin-top:.4rem;"></div>', unsafe_allow_html=True)

    dc1, dc2 = st.columns([1.1, 1.6], gap="small")
    with dc1:
        st.markdown(
            f'<div class="sf-disclosure" style="margin:0;padding:.5rem .65rem;'
            f'font-size:.76rem;line-height:1.45;">{AI_DISCLOSURE}</div>',
            unsafe_allow_html=True,
        )
    with dc2:
        disclosure_ack = st.checkbox(
            "Understood — AI disclosure will be applied",
            value=st.session_state.ws_disclosure_ack,
            key="disclosure_chk",
            disabled=_controls_locked(),
        )
    st.session_state.ws_disclosure_ack = disclosure_ack

    # ── Generate Stories ──────────────────────────────────────────────
    # Same can_generate / caption / button logic as before — now rendered
    # last (per the new target order) instead of via a reserved container
    # slot, since nothing downstream needs it to appear earlier on screen.
    can_generate = (
        consent_confirmed
        and disclosure_ack
        and bool(selected_fmts)
        and not _controls_locked()
    )

    st.markdown('<div style="margin-top:.85rem;"></div>', unsafe_allow_html=True)

    if st.session_state.ws_generating:
        st.caption("⏳ Generation in progress — controls are locked until this run finishes.")
    elif st.session_state.get("ws_confirm_discard"):
        st.caption("⚠ Resolve the pending confirmation to continue.")
    elif not consent_confirmed:
        st.caption("☑ Confirm consent to enable generation")
    elif not disclosure_ack:
        st.caption("☑ Acknowledge disclosure to enable generation")
    elif not selected_fmts:
        st.caption("Select at least one story format")

    generate_clicked = st.button(
        "⚡ Generate Stories",
        disabled=not can_generate,
        use_container_width=True,
        type="primary",
        key="generate_btn",
    )

    return selected_fmts, consent_confirmed, disclosure_ack, can_generate, generate_clicked


# ═══════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════

st.markdown(
    f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
         margin-bottom:2rem;padding-bottom:1.25rem;
         border-bottom:1px solid {c['border']};">
        <div>
            <div class="sf-page-title">✍️ Workspace</div>
            <div class="sf-page-subtitle">
                Generate, review, and edit AI-assisted impact stories
            </div>
        </div>
        <div style="font-size:.75rem;color:{c['text_muted']};text-align:right;">
            Powered by Gemini AI&nbsp;&nbsp;·&nbsp;&nbsp;Human review required
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── API gate ──────────────────────────────────────────────────────────
if not is_api_configured():
    st.error(
        "**Gemini API key not configured.**  "
        "Add `GEMINI_API_KEY` to your `.env` file and restart the app."
    )
    st.stop()


# ═══════════════════════════════════════════════════════════════════════
# LAYOUT — LEFT (participant context) / RIGHT (editorial workflow)
# ═══════════════════════════════════════════════════════════════════════

left, right = st.columns([0.9, 2.1], gap="large")


# ╔══════════════════════════════════════════════════════════════════════
# LEFT PANEL — Participant Context Sidebar  (F-05 IA revision)
# Contains ONLY: participant selector, info card, existing stories.
# Story Formats / Compliance / Generate Stories now live in the RIGHT
# panel — see below.
# ╚══════════════════════════════════════════════════════════════════════

with left:

    # ── Participant selector ──────────────────────────────────────────
    st.markdown('<div class="sf-section-label">Participant</div>', unsafe_allow_html=True)

    participants = get_all_participants()

    if not participants:
        st.markdown(
            f'<div style="color:{c["text_muted"]};font-size:.875rem;'
            f'border:1px dashed {c["border"]};border-radius:10px;'
            f'padding:1.5rem;text-align:center;">'
            f'No participants yet.<br>Add participants in the Participants page.'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # FB-03: shared helper builds display labels that are unique even when
    # two participants share a name. The selectbox options list remains
    # participant IDs — only the displayed string changes.
    options = participant_options(participants)
    # Preserve selection across reruns; select by ID to avoid duplicate-name collision
    current_pid = st.session_state.ws_selected_pid
    pid_list    = list(options.keys())
    sel_index   = (
        pid_list.index(current_pid)
        if current_pid in pid_list
        else 0
    )

    # FB-04 fix — pre-seed the widget's session-state value BEFORE
    # instantiation (legal), instead of assigning to it AFTER
    # instantiation (illegal — raises StreamlitAPIException). This
    # completes the deferred-revert pattern the previous session started
    # via ws_pending_revert_pid but never wired up.
    if st.session_state.get("ws_pending_revert_pid") is not None:
        st.session_state["ws_pid_select"] = st.session_state.ws_pending_revert_pid
        st.session_state.ws_pending_revert_pid = None

    pid = st.selectbox(
        "Select participant",
        options=pid_list,
        index=sel_index,
        format_func=lambda k: options[k],
        label_visibility="collapsed",
        key="ws_pid_select",
        disabled=_controls_locked(),
    )

    if pid != st.session_state.ws_selected_pid and not st.session_state.ws_generating:
        # FB-04 — don't discard unsaved edits silently. If the editor has
        # unsaved content, revert the widget back to the current participant
        # and ask for confirmation instead of switching immediately.
        if _has_unsaved_changes():
            st.session_state.ws_confirm_discard = {
                "action": "switch_participant",
                "target_pid": pid,
            }
            st.session_state.ws_pending_revert_pid = st.session_state.ws_selected_pid
            st.rerun()
        else:
            st.session_state.ws_selected_pid = pid
            _reset_generation()

    # FB-04 — pending "switch participant" confirmation
    _ws_confirm = st.session_state.get("ws_confirm_discard")
    if _ws_confirm and _ws_confirm.get("action") == "switch_participant":
        _target_pid   = _ws_confirm.get("target_pid")
        _target_label = options.get(_target_pid, "the selected participant")
        _outcome = _render_discard_confirm(
            f"You have unsaved draft changes. Switching to "
            f"**{_target_label}** will discard them.",
            discard_key="ws_discard_switch",
            cancel_key="ws_cancel_switch",
        )
        if _outcome == "discard":
            st.session_state.ws_selected_pid = _target_pid
            # BT-15 — reuse the existing BT-14 pre-seed mechanism so the
            # selectbox widget itself is updated to the newly committed
            # participant on the next render. Without this, ws_pid_select
            # still holds the stale, previously-reverted value, and the
            # ordinary switch-detection logic at the top of the page
            # (seeing no unsaved changes after _reset_generation()) would
            # resync ws_selected_pid back down to that stale value —
            # silently undoing this discard.
            st.session_state.ws_pending_revert_pid = _target_pid
            st.session_state.ws_confirm_discard = None
            _reset_generation()
            st.rerun()
        elif _outcome == "cancel":
            st.session_state.ws_confirm_discard = None
            st.rerun()

    # FB-04 — the page must keep operating on the committed participant
    # (ws_selected_pid) until the user explicitly confirms the switch via
    # "Discard & Continue". `pid` is the raw, possibly-uncommitted
    # selectbox value; `active_pid` is what every downstream Workspace
    # operation (context card, existing stories, save/submit) should use.
    active_pid = st.session_state.ws_selected_pid or pid

    participant = get_participant(active_pid)
    consent     = participant.get("consent_level", "full")

    # ── Participant context card ────────────────────────────────────────
    st.markdown('<div style="margin-top:.85rem;"></div>', unsafe_allow_html=True)

    program = participant.get("program") or "—"
    domain  = participant.get("domain") or ""
    email   = participant.get("email") or "—"

    st.markdown(
        f"""
        <div class="sf-card" style="margin-bottom:.75rem;">
            <div style="font-size:.95rem;font-weight:600;
                 color:{c['text_primary']};margin-bottom:.75rem;">
                {participant['name']}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;">
                <div>
                    <div style="font-size:.68rem;color:{c['text_muted']};
                         text-transform:uppercase;letter-spacing:.06em;">Program</div>
                    <div style="font-size:.82rem;color:{c['text_secondary']};margin-top:.15rem;">
                        {program}
                    </div>
                </div>
                <div>
                    <div style="font-size:.68rem;color:{c['text_muted']};
                         text-transform:uppercase;letter-spacing:.06em;">Domain</div>
                    <div style="font-size:.82rem;color:{c['text_secondary']};margin-top:.15rem;">
                        {domain or '—'}
                    </div>
                </div>
            </div>
            <div style="margin-top:.65rem;">
                <div style="font-size:.68rem;color:{c['text_muted']};
                     text-transform:uppercase;letter-spacing:.06em;">Email</div>
                <div style="font-size:.8rem;color:{c['text_secondary']};margin-top:.15rem;">
                    {email}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick data preview
    with st.expander("View participant data", expanded=False):
        for field, label in [
            ("background",   "Background"),
            ("achievements", "Achievements"),
            ("challenges",   "Challenges"),
            ("outcomes",     "Outcomes"),
        ]:
           # NEW — safe
            val = (participant.get(field) or "").strip()
            st.markdown(
                f'<div style="font-size:.7rem;color:{c["text_muted"]};'
                f'text-transform:uppercase;letter-spacing:.06em;margin-top:.65rem;">'
                f'{label}</div>'
                f'<div style="font-size:.82rem;color:{c["text_secondary"]};'
                f'margin-top:.2rem;line-height:1.6;">'
                f'{val or "<em>Not provided</em>"}</div>',
                unsafe_allow_html=True,
            )

    # ── Existing Stories ──────────────────────────────────────────────
    st.markdown('<div style="margin-top:.85rem;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-label">Existing Stories</div>', unsafe_allow_html=True)

    existing_stories = get_stories_for_participant(active_pid)

    # Separate editable vs read-only by status
    EDITABLE_STATUSES   = ("draft", "in_review", "rejected")
    READONLY_STATUSES   = ("approved", "published")

    editable_stories  = [s for s in existing_stories if s.get("status") in EDITABLE_STATUSES]
    readonly_stories  = [s for s in existing_stories if s.get("status") in READONLY_STATUSES]

    if not existing_stories:
        st.markdown(
            f'<div style="font-size:.78rem;color:{c["text_muted"]};'
            f'font-style:italic;padding:.35rem 0;">No stories saved yet for this participant.</div>',
            unsafe_allow_html=True,
        )
    else:
        # ── Editable stories → compact selectbox (FB-01) ─────────────
        # Replaces the O(N) container-per-story loop with a single
        # selectbox + one button regardless of how many versions exist.
        # Key includes pid so Streamlit auto-resets the widget on
        # participant change — no manual reset needed in _reset_generation().
        # _load_story_into_editor() is called identically to before.
        # UNCHANGED from FB-01.
        if editable_stories:
            _editable_opts: dict = {}
            for _s in editable_stories:
                _fmt  = _s.get("format", "")
                _spec = STORY_FORMATS.get(_fmt, {})
                _icon = _spec.get("icon", "\u2726")
                _lbl  = _spec.get("label", _fmt)
                _ver  = _s.get("version", 1)
                _st   = _s.get("status", "draft").replace("_", " ").title()
                _wc   = _s.get("word_count", 0) or 0
                _editable_opts[_s["id"]] = (
                    f"{_icon} {_lbl}  \u00b7  v{_ver}  \u00b7  {_st}  \u00b7  {_wc}w"
                )

            _sel_sid = st.selectbox(
                "Select story to load",
                options=list(_editable_opts.keys()),
                format_func=lambda k: _editable_opts[k],
                label_visibility="collapsed",
                key=f"ws_load_sel_{active_pid}",
                disabled=_controls_locked(),
            )

            if st.button(
                "\u21bb Load Selected Story",
                key="ws_load_selected_btn",
                use_container_width=True,
                disabled=_controls_locked(),
            ):
                _sel_story = next(
                    (_s for _s in editable_stories if _s["id"] == _sel_sid), None
                )
                if _sel_story:
                    # FB-04 — confirm before discarding unsaved edits
                    if _has_unsaved_changes():
                        st.session_state.ws_confirm_discard = {
                            "action": "load_story",
                            "story": _sel_story,
                        }
                    else:
                        _load_story_into_editor(_sel_story)
                    st.rerun()

            # FB-04 — pending "load different story" confirmation
            _ws_confirm = st.session_state.get("ws_confirm_discard")
            if _ws_confirm and _ws_confirm.get("action") == "load_story":
                _outcome = _render_discard_confirm(
                    "You have unsaved draft changes. Loading a "
                    "different story version will discard them.",
                    discard_key="ws_discard_load",
                    cancel_key="ws_cancel_load",
                )
                if _outcome == "discard":
                    _load_story_into_editor(_ws_confirm["story"])
                    st.session_state.ws_confirm_discard = None
                    st.rerun()
                elif _outcome == "cancel":
                    st.session_state.ws_confirm_discard = None
                    st.rerun()

        # ── Read-only stories (approved / published) ──────────────────
        # F-05A: collapsed into a single closed-by-default expander so
        # this section no longer grows the panel indefinitely as more
        # stories are approved/published. Row content/markup identical
        # to before — only the wrapping container changed.
        if readonly_stories:
            if editable_stories:
                st.markdown('<div style="margin-top:.5rem;"></div>', unsafe_allow_html=True)
            with st.expander(
                f"Approved / Published ({len(readonly_stories)})",
                expanded=False,
            ):
                for s in readonly_stories:
                    fmt_key  = s.get("format", "")
                    spec     = STORY_FORMATS.get(fmt_key, {})
                    fmt_icon = spec.get("icon", "✦")
                    fmt_lbl  = spec.get("label", fmt_key)
                    wc       = s.get("word_count", 0) or 0
                    status   = s.get("status", "approved")
                    ver_ro   = s.get('version', 1)

                    STATUS_FG_RO = {"approved": c["green"],  "published": c["purple"]}
                    STATUS_BG_RO = {"approved": c["green_soft"], "published": c["purple_soft"]}
                    st_fg  = STATUS_FG_RO.get(status, c["text_muted"])
                    st_bg  = STATUS_BG_RO.get(status, c["surface_alt"])
                    st_lbl = status.title()

                    # Still needs st.columns because the approved/published row
                    # shows no button — but we keep consistent visual alignment.
                    # Pure HTML row is fine here (no widget on this row).
                    st.markdown(
                        f'<div style="display:flex;align-items:center;'
                        f'padding:.3rem 0;opacity:.6;">'
                        f'<span style="display:inline-flex;align-items:center;'
                        f'padding:.1rem .4rem;border-radius:10px;background:{st_bg};'
                        f'color:{st_fg};font-size:.65rem;font-weight:600;'
                        f'margin-right:.4rem;">{st_lbl}</span>'
                        f'<span style="font-size:.78rem;color:{c["text_secondary"]};">'
                        f'{fmt_icon} {fmt_lbl}</span>'
                        f'<span style="font-size:.68rem;color:{c["text_muted"]};'
                        f'font-family:\'DM Mono\',monospace;margin-left:.4rem;">· v{ver_ro} · {wc}w</span>'
                        f'<span style="font-size:.65rem;color:{c["text_muted"]};'
                        f'margin-left:auto;font-style:italic;">view in Repository</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── Consent status — computed only (F-05 IA) ──────────────────────
    # The old hard `st.stop()` gate lived here and halted the ENTIRE
    # script the moment a non-consenting participant was selected — which
    # would now also blank the left panel we just rendered above. The
    # gate itself has to move with the workflow it gates, so only the
    # computation stays here (participant is fetched in this panel); the
    # actual warning + block now render in the RIGHT panel, immediately
    # in front of the controls it disables. Same three consent levels,
    # same warning copy, same behavior — just relocated.
    consent_ok    = consent in ("full", "anonymized", "internal")
    consent_label = CONSENT_LEVELS.get(consent, consent)


# ╔══════════════════════════════════════════════════════════════════════
# RIGHT PANEL — PART A: Editorial Workflow (context + controls)
# F-05 IA revision.
#
# Story Overview / Format Coverage / Latest Story (F-05B), Story Formats,
# Compliance, and Generate Stories all render here now, stacked above
# where the editor tabs appear. Before any stories exist for this
# session they render inline, in that order. Once tabs exist (or a run
# was cancelled), the same controls collapse into a closed expander
# above the tabs instead of disappearing — everything that used to be
# reachable stays reachable, it's just demoted visually once the editor
# takes over.
# ╚══════════════════════════════════════════════════════════════════════

with right:
    if not consent_ok:
        # Consent blocked — same warning as before, now living next to
        # the controls it disables instead of halting the whole script.
        st.markdown(
            f'<div class="sf-consent-warn" style="margin-bottom:.75rem;">'
            f'✗&nbsp;&nbsp;{consent_label}</div>',
            unsafe_allow_html=True,
        )
        st.warning(
            "This participant has not given consent. Story generation is disabled."
        )
        # Keep every variable the module-level generation-trigger logic
        # below expects defined, exactly as a blocked Generate button
        # would produce.
        selected_fmts     = st.session_state.ws_formats_sel
        consent_confirmed = False
        disclosure_ack    = False
        can_generate      = False
        generate_clicked  = False

    else:
        generated  = st.session_state.ws_generated
        edited     = st.session_state.ws_edited
        saved_ids  = st.session_state.ws_saved_ids
        ws_skipped = st.session_state.get("ws_skipped_fmts", [])

        # Same condition previously used to pick "empty state vs editor"
        # in the old RIGHT panel — reused to decide whether the full
        # pre-generation workflow renders inline, or whether the editor
        # has already taken over and controls should demote into a
        # collapsed drawer above it.
        show_overview = (
            not st.session_state.ws_generating
            and not generated
            and not ws_skipped
        )

        if show_overview:
            # ── Context: Story Overview / Format Coverage / Latest Story ──
            # (F-05B content, unchanged computation/markup — only the
            # copy in two captions was updated to say "below" instead of
            # "on the left", since the controls are now in this panel.)
            if not existing_stories:
                st.markdown(
                    f"""
                    <div style="
                        display:flex;flex-direction:column;align-items:center;
                        justify-content:center;min-height:220px;
                        border:1.5px dashed {c['border']};border-radius:14px;
                        padding:2.25rem;text-align:center;margin-bottom:1.5rem;
                    ">
                        <div style="font-size:2rem;margin-bottom:1rem;">✦</div>
                        <div style="font-size:1.05rem;font-weight:600;
                             color:{c['text_primary']};margin-bottom:.5rem;">
                            No stories yet for {participant['name']}
                        </div>
                        <div style="font-size:.875rem;color:{c['text_muted']};
                             max-width:360px;line-height:1.7;">
                            Confirm compliance, choose formats below, then click
                            <strong style="color:{c['accent']};">Generate Stories</strong>
                            to begin.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                # Story history exists — surface it instead of a generic box.
                _total_existing = len(existing_stories)

                # Status breakdown — reuses status_badge() from components.badges
                _status_counts = {}
                for _s in existing_stories:
                    _k = _s.get("status", "draft")
                    _status_counts[_k] = _status_counts.get(_k, 0) + 1
                _status_html = "".join(
                    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
                    f'margin:0 .5rem .3rem 0;">'
                    + status_badge(_k)
                    + f'<span style="font-size:.72rem;color:{c["text_muted"]};">'
                      f'\u00d7{_v}</span></span>'
                    for _k, _v in _status_counts.items()
                )

                st.markdown('<div class="sf-section-label">Story Overview</div>', unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="sf-card" style="margin-bottom:1rem;">
                        <div style="font-size:.95rem;font-weight:600;
                             color:{c['text_primary']};margin-bottom:.65rem;">
                            {participant['name']} &nbsp;\u00b7&nbsp;
                            {_total_existing} {'story' if _total_existing == 1 else 'stories'} so far
                        </div>
                        <div>{_status_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Format coverage — which of the 4 fixed formats already exist
                _covered_fmts = {_s.get("format") for _s in existing_stories}
                _fmt_rows = ""
                for _fk, _spec in STORY_FORMATS.items():
                    _has = _fk in _covered_fmts
                    _fmt_rows += (
                        f'<div style="display:flex;align-items:center;gap:.5rem;'
                        f'padding:.35rem 0;border-bottom:1px solid {c["border"]};">'
                        + format_badge(_fk)
                        + (
                            f'<span style="font-size:.72rem;color:{c["green"]};'
                            f'margin-left:auto;">\u2713 generated</span>'
                            if _has else
                            f'<span style="font-size:.72rem;color:{c["text_muted"]};'
                            f'margin-left:auto;">not yet generated</span>'
                        )
                        + '</div>'
                    )

                # Latest story — most recently updated
                _latest = max(
                    existing_stories,
                    key=lambda s: s.get("updated_at") or s.get("created_at") or "",
                )
                _latest_content = (_latest.get("content") or "").strip()
                _latest_preview = _latest_content[:160]
                if len(_latest_content) > 160:
                    _latest_preview += "\u2026"

                # F-05C/C3: Format Coverage and Latest Story render
                # side-by-side instead of stacked.
                fc_col, ls_col = st.columns(2, gap="medium")

                with fc_col:
                    st.markdown('<div class="sf-section-label">Format Coverage</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="sf-card" style="margin-bottom:1rem;height:calc(100% - 1rem);">{_fmt_rows}</div>',
                        unsafe_allow_html=True,
                    )

                with ls_col:
                    st.markdown('<div class="sf-section-label">Latest Story</div>', unsafe_allow_html=True)
                    st.markdown(
                        f"""
                        <div class="sf-card" style="margin-bottom:1rem;height:calc(100% - 1rem);">
                            <div style="display:flex;align-items:center;gap:.6rem;
                                 margin-bottom:.6rem;flex-wrap:wrap;">
                                {format_badge(_latest.get('format', ''))}
                                {status_badge(_latest.get('status', 'draft'))}
                                <span style="font-size:.72rem;color:{c['text_muted']};margin-left:auto;">
                                    {_latest.get('word_count', 0) or 0} words
                                </span>
                            </div>
                            <div style="font-size:.83rem;color:{c['text_secondary']};
                                 line-height:1.6;font-style:italic;">
                                "{_latest_preview or 'No content.'}"
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="font-size:.8rem;color:{c["text_muted"]};'
                    f'margin-top:.25rem;margin-bottom:.5rem;text-align:center;">'
                    f'Choose formats below and click '
                    f'<strong style="color:{c["accent"]};">Generate Stories</strong> '
                    f'to create a new version.</div>',
                    unsafe_allow_html=True,
                )

            # ── Configure + comply + generate — inline, full workflow ──
            st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
            (
                selected_fmts,
                consent_confirmed,
                disclosure_ack,
                can_generate,
                generate_clicked,
            ) = _render_generate_controls()

        else:
            # Editor already active (tabs) or a run was just cancelled —
            # keep the same controls reachable, demoted into a closed
            # drawer above the tabs instead of competing with the editor
            # for attention.
            with st.expander("⚙️ Story Formats & Generate", expanded=False):
                (
                    selected_fmts,
                    consent_confirmed,
                    disclosure_ack,
                    can_generate,
                    generate_clicked,
                ) = _render_generate_controls()


# ╔══════════════════════════════════════════════════════════════════════
# GENERATION — triggered from the RIGHT panel's workflow controls above
# ╚══════════════════════════════════════════════════════════════════════

if generate_clicked and can_generate:
    # Reentrancy guard — fixes Bug 3 (overlapping generations). If a
    # second script run somehow reaches this point while a previous run's
    # generation is still considered active, refuse to start a second
    # Gemini sequence.
    if st.session_state.ws_generating:
        with right:
            st.warning("A generation run is already in progress. Please wait for it to finish.")
        st.stop()

    # FB-04 — confirm before discarding unsaved edits currently sitting
    # in the editor (ws_edited), since _reset_generation() below wipes them.
    if _has_unsaved_changes():
        st.session_state.ws_confirm_discard = {
            "action": "generate",
            "formats": list(selected_fmts),
        }
        st.rerun()
    else:
        # Two-run pattern — fixes the race where generation started in the
        # SAME script run that drew the controls. Streamlit paints once per
        # run; flipping ws_generating mid-run does not retroactively disable
        # widgets that already rendered earlier in that same run. So:
        #   run N   : click detected → set ws_pending + ws_generating → rerun
        #   run N+1 : top-of-script sees ws_generating=True → every gated
        #             widget renders disabled → THIS run performs the actual
        #             Gemini call, guarded by ws_pending so it fires once.
        _reset_generation()
        st.session_state.ws_pending    = list(selected_fmts)
        st.session_state.ws_total_fmts = len(selected_fmts)
        st.session_state.ws_generating = True
        st.rerun()

# FB-04 — pending "start generation" confirmation
_ws_confirm = st.session_state.get("ws_confirm_discard")
if _ws_confirm and _ws_confirm.get("action") == "generate" and not st.session_state.ws_generating:
    with right:
        _outcome = _render_discard_confirm(
            "You have unsaved draft changes. Generating new stories "
            "will discard them.",
            discard_key="ws_discard_generate",
            cancel_key="ws_cancel_generate",
        )
    if _outcome == "discard":
        _confirmed_formats = _ws_confirm.get("formats") or selected_fmts
        st.session_state.ws_confirm_discard = None
        _reset_generation()
        st.session_state.ws_pending    = list(_confirmed_formats)
        st.session_state.ws_total_fmts = len(_confirmed_formats)
        st.session_state.ws_generating = True
        st.rerun()
    elif _outcome == "cancel":
        st.session_state.ws_confirm_discard = None
        st.rerun()


_ws_pending = st.session_state.get("ws_pending")
if st.session_state.ws_generating and _ws_pending:
    _remaining  = list(_ws_pending)
    _total      = st.session_state.get("ws_total_fmts") or len(_remaining)
    _done_count = _total - len(_remaining)

    # ── Generate one format per rerun ─────────────────────────────────
    _current_fmt   = _remaining[0]
    _remaining_rest = _remaining[1:]
    _cur_spec      = STORY_FORMATS.get(_current_fmt, {})

    with right:
        st.markdown(
            f'<div class="sf-section-label">Generation Progress</div>',
            unsafe_allow_html=True,
        )

        # Progress bar: formats completed so far / total
        _pct = int((_done_count / _total) * 100) if _total else 0
        st.progress(_pct)

        # Build status log: past formats + current
        _status_lines = []
        for _prev_fmt, _prev_res in st.session_state.ws_generated.items():
            _prev_spec = STORY_FORMATS.get(_prev_fmt, {})
            _tick = "✅" if ("content" in _prev_res and "error" not in _prev_res) else "⚠️"
            _status_lines.append(
                f'{_tick}&nbsp;&nbsp;<strong>{_prev_spec.get("label", _prev_fmt)}</strong>'
                f'&nbsp;—&nbsp;done'
            )
        _status_lines.append(
            f'⏳&nbsp;&nbsp;<strong>{_cur_spec.get("label", _current_fmt)}</strong>'
            f'&nbsp;({_done_count + 1}/{_total})…'
        )
        st.markdown(
            f'<div class="sf-generation-status">'
            + "<br>".join(_status_lines)
            + '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="margin-top:.75rem;"></div>', unsafe_allow_html=True)

        # Cancel button — on_click sets flag; flag is checked at the TOP
        # of the NEXT rerun (after the current API call finishes), so the
        # current format completes and subsequent ones are skipped.
        def _request_cancel():
            st.session_state.ws_cancel_requested = True

        st.button(
            "⛔ Cancel Generation",
            key="ws_cancel_btn",
            on_click=_request_cancel,
            use_container_width=True,
        )

    # ── Actual Gemini call ─────────────────────────────────────────────
    try:
        _result = generate_story(participant, _current_fmt)
    except Exception as _exc:
        _result = {"error": f"Unexpected error during generation: {_exc}"}

    # Store result regardless of success/error
    st.session_state.ws_generated[_current_fmt] = _result
    if "content" in _result:
        st.session_state.ws_edited[_current_fmt] = _result["content"]
        _bump_gen_counter(_current_fmt)

    if _remaining_rest:
        # More formats to go — pace the next call and loop via rerun
        st.session_state.ws_pending = _remaining_rest
        time.sleep(settings.GEMINI_SEQUENTIAL_DELAY)
        st.rerun()
    else:
        # All formats done normally
        st.session_state.ws_pending      = None
        st.session_state.ws_generating   = False
        st.session_state.ws_skipped_fmts = []
        st.rerun()


# ╔══════════════════════════════════════════════════════════════════════
# INLINE REGENERATION — Retry (error case) / Regenerate (success case)
# ╚══════════════════════════════════════════════════════════════════════
#
# WS-02 / WS-03 / WS-04 / WS-05 fix.
# This block mirrors the exact two-run pattern already used for the main
# Generate button above: the buttons below only set state and rerun;
# the actual blocking Gemini call happens here, at the top of the next
# run — after every other control has already redrawn itself disabled.
_inline_fmt = st.session_state.get("ws_inline_pending")
if st.session_state.ws_generating and _inline_fmt:
    _spec = STORY_FORMATS.get(_inline_fmt, {})
    with right:
        st.markdown('<div class="sf-section-label">Generation Progress</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sf-generation-status">⏳&nbsp;&nbsp;Regenerating '
            f'<strong>{_spec.get("label", _inline_fmt)}</strong>…</div>',
            unsafe_allow_html=True,
        )

        try:
            res = generate_story(participant, _inline_fmt)
        except Exception as exc:
            res = {"error": f"Unexpected error during generation: {exc}"}
        finally:
            st.session_state.ws_generating = False
            st.session_state.ws_inline_pending = None

        st.session_state.ws_generated[_inline_fmt] = res
        if "content" in res:
            st.session_state.ws_edited[_inline_fmt] = res["content"]
            _bump_gen_counter(_inline_fmt)
            if "error" in res:
                st.warning("Regenerated, but the response needed a partial-content fallback — review before saving.")
            else:
                st.success(f"{_spec.get('label', _inline_fmt)} regenerated.")
        else:
            st.error(f"Regeneration failed: {res.get('error', 'Unknown error')}")

        time.sleep(0.4)
        st.rerun()


# ╔══════════════════════════════════════════════════════════════════════
# RIGHT PANEL — PART B: Editor (tabs, save/submit/regenerate, bulk actions)
# F-05 IA revision — Part A above already rendered the context cards /
# empty hero state / collapsed-controls drawer as appropriate, so this
# block now only needs to handle the "stories exist this session" case.
# Tab/editor/save/submit/regenerate/bulk-action logic is completely
# unchanged from before this revision.
# ╚══════════════════════════════════════════════════════════════════════

with right:
    if not consent_ok:
        pass  # warning already rendered by Part A above

    elif st.session_state.ws_generating:
        pass  # progress already rendered by the GENERATION block above

    elif not st.session_state.ws_generated and not st.session_state.get("ws_skipped_fmts", []):
        pass  # context + controls already rendered by Part A above

    else:
        generated  = st.session_state.ws_generated
        edited     = st.session_state.ws_edited
        saved_ids  = st.session_state.ws_saved_ids
        ws_skipped = st.session_state.get("ws_skipped_fmts", [])

        # ── Cancel summary banner — shown when cancel was requested ───
        # Compact, single-row chip strip rather than a tall two-section
        # alert block — this is status metadata, not the primary work
        # area, so it recedes behind the editor tabs that follow it.
        if ws_skipped:
            _total_fmts = len(generated) + len(ws_skipped)
            _chips = "".join(
                f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
                f'font-size:.78rem;color:{c["green"]};margin-right:1rem;">'
                f'✓&nbsp;{STORY_FORMATS.get(f, {}).get("label", f)}</span>'
                for f in generated
            ) + "".join(
                f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
                f'font-size:.78rem;color:{c["text_muted"]};margin-right:1rem;">'
                f'✕&nbsp;{STORY_FORMATS.get(f, {}).get("label", f)}</span>'
                for f in ws_skipped
            )
            st.markdown(
                f'<div style="border-left:3px solid {c["amber"]};'
                f'background:{c["surface_alt"]};border-radius:0 8px 8px 0;'
                f'padding:.6rem .9rem;margin-bottom:1.25rem;">'
                f'<div style="font-size:.8rem;font-weight:600;color:{c["amber"]};'
                f'margin-bottom:.35rem;">'
                f'⚠&nbsp;&nbsp;Generation cancelled &nbsp;·&nbsp; '
                f'{len(generated)}/{_total_fmts} completed</div>'
                f'<div>{_chips}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        # ── Story tabs — only when at least one format completed ─────
        fmt_keys   = list(generated.keys())
        tab_labels = [
            f"{STORY_FORMATS[f]['icon']} {STORY_FORMATS[f]['label']}"
            for f in fmt_keys
        ]
        tabs = st.tabs(tab_labels) if fmt_keys else []

        for tab, fmt in zip(tabs, fmt_keys):
            with tab:
                result   = generated[fmt]
                spec     = STORY_FORMATS[fmt]
                wmin, wmax = spec["word_range"]
                sid      = saved_ids.get(fmt)

                # ── Story has error ───────────────────────────────────
                if "error" in result and "content" not in result:
                    st.markdown(
                        f"""
                        <div style="
                            background:{c['red_soft']};border:1px solid {c['red']};
                            border-radius:10px;padding:1.25rem;
                            color:{c['red']};font-size:.875rem;margin-bottom:1rem;
                        ">
                            <strong>Generation failed</strong><br>
                            <span style="color:{c['text_muted']};font-size:.8rem;">
                                {result['error']}
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if st.button(
                        "↻ Retry this format",
                        key=f"retry_{fmt}",
                        use_container_width=False,
                        type="primary",
                        disabled=_controls_locked(),
                    ):
                        # Two-run pattern (see inline regeneration block above)
                        # — set state and rerun BEFORE calling Gemini, so
                        # every other control renders disabled on the run
                        # that actually makes the blocking call.
                        st.session_state.ws_inline_pending = fmt
                        st.session_state.ws_generating = True
                        st.rerun()
                    continue

                # ── Story content ─────────────────────────────────────

                # FB-05: Compact metadata strip — replaces the two-column
                # status-badge / word-count toolbar with a single HTML flex
                # row that surfaces format, version, status, origin, and
                # word count without adding vertical height.
                #
                # The existing get_story(sid) call (already required to read
                # live status) is extended to also read version and
                # batch_job_id from the same returned dict.
                # Zero additional DB queries; zero new session state.
                current_text = edited.get(fmt, result.get("content", ""))
                wc           = count_words(current_text)

                status_val  = "draft"
                version_str = None        # None → unsaved new generation
                origin_str  = "Workspace"

                if sid:
                    from services.db_service import get_story
                    db_story = get_story(sid)
                    if db_story:
                        status_val  = db_story["status"]
                        version_str = f"v{db_story.get('version', 1)}"
                        origin_str  = "Batch" if db_story.get("batch_job_id") else "Workspace"

                _ver_html = (
                    f'<span style="font-size:.72rem;font-family:\'DM Mono\',monospace;'
                    f'color:{c["text_muted"]};padding:.18rem .5rem;'
                    f'background:{c["surface_alt"]};border-radius:6px;'
                    f'border:1px solid {c["border"]};">{version_str}</span>'
                    if version_str else
                    f'<span style="font-size:.72rem;color:{c["amber"]};'
                    f'padding:.18rem .5rem;background:{c["amber_soft"]};'
                    f'border-radius:6px;border:1px solid {c["amber"]};">'
                    f'New\u00a0\u00b7\u00a0Unsaved</span>'
                )
                _orig_color  = c["accent"]      if origin_str == "Batch" else c["text_muted"]
                _orig_bg     = c["accent_soft"] if origin_str == "Batch" else c["surface_alt"]
                _orig_border = c["accent"]      if origin_str == "Batch" else c["border"]
                _orig_html = (
                    f'<span style="font-size:.72rem;color:{_orig_color};'
                    f'padding:.18rem .5rem;background:{_orig_bg};border-radius:6px;'
                    f'border:1px solid {_orig_border};">{origin_str}</span>'
                )
                _sep = (
                    f'<span style="color:{c["border"]};font-size:.8rem;'
                    f'margin:0 .05rem;">|</span>'
                )

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:.5rem;'
                    f'padding:.45rem 0 .65rem 0;flex-wrap:wrap;">'
                    f'<span style="font-size:.82rem;font-weight:600;'
                    f'color:{c["text_secondary"]};">'
                    f'{spec["icon"]}&nbsp;{spec["label"]}</span>'
                    f'{_sep}{_ver_html}{_sep}'
                    + status_badge(status_val)
                    + f'{_sep}{_orig_html}{_sep}'
                    + word_count_indicator(wc, wmin, wmax)
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                # Inline editor — key includes the per-format generation counter
                # so a fresh Generate/Regenerate/Retry/Load always shows up,
                # instead of Streamlit silently re-serving the old cached text
                # for a key it has already seen.
                _gen_key = st.session_state.ws_gen_counter.get(fmt, 0)
                new_text = st.text_area(
                    "Story content",
                    value=current_text,
                    height=320,
                    key=f"editor_{fmt}_{_gen_key}",
                    label_visibility="collapsed",
                    placeholder=f"Generated {spec['label']} content will appear here…",
                    disabled=_controls_locked(),
                )
                st.session_state.ws_edited[fmt] = new_text

                # Live word count update
                live_wc = count_words(new_text)
                st.markdown(
                    f'<div style="text-align:right;margin-top:.3rem;">'
                    + word_count_indicator(live_wc, wmin, wmax)
                    + '</div>',
                    unsafe_allow_html=True,
                )

                # Editor notes
                editor_notes = st.text_input(
                    "Editor notes (optional)",
                    key=f"notes_{fmt}",
                    placeholder="Add internal notes for reviewers…",
                    disabled=_controls_locked(),
                )

                # ── Action row ────────────────────────────────────────
                st.markdown('<div style="margin:.65rem 0 .3rem 0;"></div>', unsafe_allow_html=True)
                a1, a2, a3, _ = st.columns([2, 2, 2, 3], gap="small")

                with a1:
                    if st.button(
                        "💾 Save Draft",
                        key=f"save_{fmt}",
                        use_container_width=True,
                        disabled=_controls_locked(),
                    ):
                        data = {
                            "id":               None,  # always INSERT — full version history
                            "participant_id":   active_pid,
                            "format":           fmt,
                            "content":          new_text,
                            "status":           "draft",
                            "editor_notes":     editor_notes,
                            "ai_model":         "gemini-2.5-flash",
                            "generation_prompt": result.get("prompt", ""),
                        }
                        new_sid = save_story(data)
                        st.session_state.ws_saved_ids[fmt] = new_sid
                        st.session_state.ws_saved_baseline[fmt] = new_text  # FB-04
                        # BT-10: rerun so the left panel's Existing Stories
                        # section re-fetches from DB and shows the new version
                        # immediately.
                        st.rerun()

                with a2:
                    can_submit = bool(new_text.strip()) and not _controls_locked()
                    if st.button(
                        "📋 Submit for Review",
                        key=f"submit_{fmt}",
                        disabled=not can_submit,
                        use_container_width=True,
                        type="primary",
                    ):
                        # BT-06: version is immutable, status is mutable.
                        # If this format was already saved this session, reuse
                        # that row — update its status only. No second INSERT.
                        # If not yet saved, do exactly one INSERT then update.
                        _existing_sid = st.session_state.ws_saved_ids.get(fmt)
                        if _existing_sid:
                            update_story_status(_existing_sid, "in_review")
                        else:
                            data = {
                                "id":               None,
                                "participant_id":   active_pid,
                                "format":           fmt,
                                "content":          new_text,
                                "status":           "draft",
                                "editor_notes":     editor_notes,
                                "ai_model":         "gemini-2.5-flash",
                                "generation_prompt": result.get("prompt", ""),
                            }
                            _existing_sid = save_story(data)
                            st.session_state.ws_saved_ids[fmt] = _existing_sid
                            update_story_status(_existing_sid, "in_review")
                        st.session_state.ws_saved_baseline[fmt] = new_text  # FB-04
                        st.success("Submitted to Review Queue.")
                        st.rerun()

                with a3:
                    if st.button(
                        "↻ Regenerate",
                        key=f"regen_{fmt}",
                        use_container_width=True,
                        disabled=_controls_locked(),
                    ):
                        st.session_state.ws_inline_pending = fmt
                        st.session_state.ws_generating = True
                        st.rerun()

                # ── AI Disclosure banner ──────────────────────────────
                st.markdown('<div style="margin-top:.85rem;"></div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="sf-disclosure" style="padding:.55rem .8rem;'
                    f'font-size:.78rem;line-height:1.5;">{AI_DISCLOSURE}</div>',
                    unsafe_allow_html=True,
                )

        # ── Bulk action bar ───────────────────────────────────────────
        st.markdown(
            '<hr style="border-color:rgba(255,255,255,0.055);margin:1.75rem 0 1.1rem 0;">',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sf-section-label" style="margin-bottom:.5rem;">Publishing Actions</div>',
            unsafe_allow_html=True,
        )

        bc1, bc2, bc3 = st.columns([2, 2, 5], gap="small")

        with bc1:
            if st.button(
                "💾 Save All Drafts",
                use_container_width=True,
                key="save_all",
                disabled=_controls_locked(),
            ):
                count = 0
                for fmt in fmt_keys:
                    res = generated.get(fmt, {})
                    if "content" not in res:
                        continue
                    content = edited.get(fmt, res["content"])
                    if not content.strip():
                        continue
                    data = {
                        "id":             None,  # always INSERT — full version history
                        "participant_id": active_pid,
                        "format":         fmt,
                        "content":        content,
                        "status":         "draft",
                        "editor_notes":   "",
                        "ai_model":       "gemini-2.5-flash",
                        "generation_prompt": res.get("prompt", ""),
                    }
                    new_sid = save_story(data)
                    st.session_state.ws_saved_ids[fmt] = new_sid
                    st.session_state.ws_saved_baseline[fmt] = content  # FB-04
                    count += 1
                # BT-10: rerun so the left panel's Existing Stories section
                # re-fetches from DB and shows all newly saved versions immediately.
                st.rerun()

        with bc2:
            if st.button(
                "📋 Submit All for Review",
                use_container_width=True,
                key="submit_all",
                type="primary",
                disabled=_controls_locked(),
            ):
                count = 0
                for fmt in fmt_keys:
                    res = generated.get(fmt, {})
                    if "content" not in res:
                        continue
                    content = edited.get(fmt, res["content"])
                    if not content.strip():
                        continue
                    # BT-06: same rule as per-format Submit — reuse the
                    # already-saved sid if it exists, only INSERT if not.
                    _existing_sid = st.session_state.ws_saved_ids.get(fmt)
                    if _existing_sid:
                        update_story_status(_existing_sid, "in_review")
                    else:
                        data = {
                            "id":             None,
                            "participant_id": active_pid,
                            "format":         fmt,
                            "content":        content,
                            "status":         "draft",
                            "editor_notes":   "",
                            "ai_model":       "gemini-2.5-flash",
                            "generation_prompt": res.get("prompt", ""),
                        }
                        _existing_sid = save_story(data)
                        st.session_state.ws_saved_ids[fmt] = _existing_sid
                        update_story_status(_existing_sid, "in_review")
                    st.session_state.ws_saved_baseline[fmt] = content  # FB-04
                    count += 1
                st.success(f"Submitted {count} story/stories to Review Queue.")
                st.rerun()