"""
StoryForge — Data Sources  (MVP)
─────────────────────────────────
Lightweight evidence-to-participant ingestion. Paste raw text (LinkedIn
post, internship review, training/certification review) → Gemini
extracts an editorial participant profile → editor reviews/edits →
saved via the SAME upsert_participant() path used by Participants'
Add/Edit tab.

No new tables. No new services. No story generation here.
Workflow continues exactly as before once the participant is saved.
"""

import streamlit as st

from components.theme    import page_config, apply_theme, COLORS
from services.db_service import upsert_participant, email_exists
from services.gemini_service import extract_participant_from_text, is_api_configured
from core.constants import PROGRAMS, DOMAINS, CONSENT_LEVELS
from core.database  import init_db

# ── Boot ──────────────────────────────────────────────────────────────
init_db()
page_config("Data Sources")
apply_theme()
from components.sidebar import render_sidebar
render_sidebar()
c = COLORS

# ── Session state ─────────────────────────────────────────────────────
if "evi_extracted_fields" not in st.session_state:
    st.session_state.evi_extracted_fields = None

EVIDENCE_TYPES = {
    "linkedin_post":     "LinkedIn Post",
    "internship_review": "Internship Review",
    "training_review":   "Training / Certification Review",
}

# ── Page header ───────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;
         margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div>
            <div class="sf-page-title">Data Sources</div>
            <div class="sf-page-subtitle">Extract participant profiles from pasted evidence — LinkedIn posts, reviews, and testimonials</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not is_api_configured():
    st.error(
        "**Gemini API key not configured.** "
        "Add `GEMINI_API_KEY` to your `.env` file and restart the app."
    )
    st.stop()

# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Paste evidence
# ══════════════════════════════════════════════════════════════════════

st.markdown('<div class="sf-section-label">Source</div>', unsafe_allow_html=True)

evi_type = st.selectbox(
    "Evidence type",
    options=list(EVIDENCE_TYPES.keys()),
    format_func=lambda k: EVIDENCE_TYPES[k],
    label_visibility="collapsed",
    key="evi_type_select",
)

raw_text = st.text_area(
    "Paste the raw text here",
    height=220,
    placeholder="Paste a LinkedIn post, internship review, or training/certification review...",
    key="evi_raw_text",
    label_visibility="collapsed",
)

extract_clicked = st.button(
    "✨ Extract Participant Info",
    use_container_width=True,
    type="primary",
    disabled=not raw_text.strip(),
)

if extract_clicked:
    with st.spinner("Extracting participant profile…"):
        result = extract_participant_from_text(evi_type, raw_text)
    if "error" in result:
        st.error(result["error"])
        st.session_state.evi_extracted_fields = None
    else:
        st.session_state.evi_extracted_fields = result["fields"]
        if result["fields"].get("name"):
            st.success("Extraction complete — review and edit the profile below before saving.")
        else:
            # Expected/common case: LinkedIn post bodies rarely include the
            # author's name. Extraction still succeeded — just nudge the
            # editor to fill in the one field the source text couldn't provide.
            st.success(
                "Extraction complete — review the profile below. "
                "This source didn't include a participant name, so please add it manually."
            )

# ══════════════════════════════════════════════════════════════════════
# STEP 2 — Review / edit extracted profile (same shape as Participants
# Add/Edit tab), then save via upsert_participant()
# ══════════════════════════════════════════════════════════════════════

prefill = st.session_state.get("evi_extracted_fields")

if prefill:
    st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sf-section-label">Review Extracted Profile</div>', unsafe_allow_html=True)

    # Program select (outside form — "Other" conditional needs rerun,
    # same pattern as Participants Add/Edit)
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
        key="evi_program_choice",
    )
    if program_choice == "Other (type below)":
        program = st.text_input(
            "Enter custom program name",
            value="" if prefill_prog in PROGRAMS else prefill_prog,
            key="evi_program_custom",
        )
    else:
        program = program_choice

    with st.form("evi_review_form", enter_to_submit=False, clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            # Name wasn't reliably present in the source — mark it clearly
            # as the one field that usually needs manual entry.
            _name_label = "Full Name *" if prefill.get("name") else "Full Name * (not found — please enter manually)"
            name = st.text_input(_name_label, value=prefill.get("name", ""), key="evi_name")
            email = st.text_input("Email", value=prefill.get("email", ""), key="evi_email")
            linkedin_url = st.text_input(
                "LinkedIn Profile URL (optional)",
                value=prefill.get("linkedin_url", ""),
                placeholder="https://linkedin.com/in/username",
                key="evi_linkedin",
            )
        with col2:
            domain_list    = [""] + DOMAINS
            prefill_domain = prefill.get("domain") or ""
            domain_idx     = (
                domain_list.index(prefill_domain)
                if prefill_domain in domain_list else 0
            )
            domain = st.selectbox("Domain", domain_list, index=domain_idx, key="evi_domain")

            consent_keys = list(CONSENT_LEVELS.keys())
            consent = st.selectbox(
                "Consent Level",
                options=consent_keys,
                index=0,
                format_func=lambda k: CONSENT_LEVELS[k],
                key="evi_consent",
                help="Not stated in the source text — confirm with the participant before saving.",
            )

        st.markdown('<div style="margin-top:.75rem;"></div>', unsafe_allow_html=True)

        background = st.text_area(
            "Background", value=prefill.get("background", ""), height=90, key="evi_background",
        )
        achievements = st.text_area(
            "Key Achievements", value=prefill.get("achievements", ""), height=90, key="evi_achievements",
        )
        challenges = st.text_area(
            "Challenges Overcome", value=prefill.get("challenges", ""), height=90, key="evi_challenges",
        )
        outcomes = st.text_area(
            "Outcomes & Impact", value=prefill.get("outcomes", ""), height=90, key="evi_outcomes",
        )

        submitted = st.form_submit_button("Save Participant", use_container_width=True)

    if submitted:
        _email_val = email.strip() or None

        if not name.strip():
            st.error("Name is required before saving — this source text didn't include one, so please enter it above.")
        elif program_choice == "Other (type below)" and not program.strip():
            st.error("Please enter a custom program name, or choose an existing program.")
        elif _email_val and email_exists(_email_val):
            st.error(
                f"The email **{_email_val}** is already registered to another participant. "
                "Please use a different email or leave it blank."
            )
        else:
            payload = {
                "name":          name.strip(),
                "email":         _email_val,
                "program":       (program or "").strip() or None,
                "domain":        domain or None,
                "background":    background.strip(),
                "achievements":  achievements.strip(),
                "challenges":    challenges.strip(),
                "outcomes":      outcomes.strip(),
                "consent_level": consent,
                "linkedin_url":  linkedin_url.strip() or None,
            }
            upsert_participant(payload)
            st.success(f"Participant '{name.strip()}' saved successfully.")

            # Clear state — same reset behavior as Participants Add/Edit
            st.session_state.evi_extracted_fields = None
            st.rerun()
else:
    st.markdown(
        f'<div style="text-align:center;padding:2.5rem;color:{c["text_muted"]};'
        f'border:1.5px dashed {c["border"]};border-radius:12px;margin-top:1.5rem;">'
        f'Paste evidence above and click <strong>Extract Participant Info</strong> to begin.'
        f'</div>',
        unsafe_allow_html=True,
    )