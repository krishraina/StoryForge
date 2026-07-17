"""
StoryForge — Repository  (Phase 6F)
"""
import streamlit as st
from streamlit.components.v1 import html as st_html
from components.theme    import page_config, apply_theme, COLORS
from components.badges   import status_badge, format_badge
from services.db_service import get_all_stories, update_story_status, delete_story
from core.constants      import STORY_FORMATS, STORY_STATUSES
from core.database       import init_db
from core.timeutils      import display_date

init_db()
page_config("Repository")
apply_theme()
c = COLORS
from components.sidebar import render_sidebar
render_sidebar()

if "repo_confirm_delete" not in st.session_state:
    st.session_state.repo_confirm_delete = None
# BT-05 refinement: deep-link from Batch Operations sets this to a story id;
# Repository auto-expands the matching expander, then immediately clears the
# key so subsequent reruns (user actions inside Repository) behave normally.
if "repo_open_story_id" not in st.session_state:
    st.session_state.repo_open_story_id = None
st.markdown(
    f"""
    <div style="margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid {c['border']};">
        <div class="sf-page-title">📚 Repository</div>
        <div class="sf-page-subtitle">Searchable archive of all impact stories — mark approved stories as published here</div>
    </div>
    """,
    unsafe_allow_html=True,
)

all_stories = get_all_stories()

# ── P-09 — Repository Duplicate Participant Identification ─────────────
# get_all_stories() already joins participants and returns
# participant_name / program / domain / participant_id on every story —
# no query change needed. Frequency is computed against the full,
# unfiltered result set so the disambiguator stays stable as the editor
# changes search/format/status filters, instead of flickering on/off
# depending on what's currently visible.
_repo_name_freq: dict = {}
for _rs in all_stories:
    _rn = _rs.get("participant_name", "")
    _repo_name_freq[_rn] = _repo_name_freq.get(_rn, 0) + 1


def _repo_disambiguator(story: dict) -> str:
    """
    Compact secondary identifier for a duplicate-named participant.
    Same fallback order as components.badges.participant_options()
    (domain → program → #id) minus email, since the Repository query
    doesn't select participants.email and none is added here per the
    "extend only if required" constraint — domain/program already
    disambiguate every duplicate-name case in the current dataset.
    """
    if story.get("domain"):
        return story["domain"]
    if story.get("program"):
        return story["program"][:35]
    return f"#{story.get('participant_id')}"


# ── Filters ───────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns(3)
with fc1:
    search = st.text_input("Search", placeholder="Participant name, keyword…", label_visibility="collapsed")
with fc2:
    fmt_filter = st.selectbox(
        "Format",
        ["All formats"] + list(STORY_FORMATS.keys()),
        format_func=lambda k: "All formats" if k == "All formats" else STORY_FORMATS[k]["label"],
        label_visibility="collapsed",
        key="repo_fmt_filter",
    )
with fc3:
    # FB-03: status list now sourced from STORY_STATUSES (canonical list)
    # instead of a hardcoded tuple — verified identical display order.
    status_filter = st.selectbox(
        "Status",
        ["All statuses"] + list(STORY_STATUSES.keys()),
        format_func=lambda s: "All statuses" if s == "All statuses" else s.replace("_", " ").title(),
        label_visibility="collapsed",
        key="repo_status_filter",
    )

# ── Filter stories ────────────────────────────────────────────────────
filtered = all_stories
if search:
    q = search.lower()
    filtered = [s for s in filtered if q in s.get("participant_name","").lower() or q in (s.get("content","") or "").lower()]
if fmt_filter != "All formats":
    filtered = [s for s in filtered if s["format"] == fmt_filter]
if status_filter != "All statuses":
    filtered = [s for s in filtered if s["status"] == status_filter]

st.markdown(
    f'<div style="font-size:.8rem;color:{c["text_muted"]};margin:.75rem 0 1rem 0;">'
    f'{len(filtered)} of {len(all_stories)} stories'
    f'</div>',
    unsafe_allow_html=True,
)

if not filtered:
    if not all_stories:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">'
            f'<div style="font-size:.95rem;font-weight:600;color:{c["text_primary"]};margin-bottom:.4rem;">'
            f'No stories available yet.</div>'
            f'<div style="font-size:.85rem;">Generate your first story in Workspace.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{c["text_muted"]};">No stories match your filters.</div>',
            unsafe_allow_html=True,
        )
else:
    # BT-05 refinement — capture the deep-link target written by Batch
    # Operations ("View in Repository" button sets repo_open_story_id).
    # Capture it into a local variable, then immediately clear the session
    # key. This means:
    #   • THIS render: _target_sid drives expanded=True for the match.
    #   • NEXT render (any user action in Repository): key is None, all
    #     expanders revert to their default closed state.
    # Clearing inside the same render (not a callback) does NOT trigger
    # a rerun — it just queues the new value for the next script execution.
    _target_sid = st.session_state.get("repo_open_story_id")
    if _target_sid:
        st.session_state["repo_open_story_id"] = None

    for story in filtered:
        spec    = STORY_FORMATS.get(story["format"], {})
        content = (story.get("content") or "").strip()
        status  = story["status"]

        # P-09 — only duplicate-named participants get the extra
        # identifier; everyone else's row is unchanged, so this stays
        # compact and doesn't clutter the common case.
        _repo_display_name = story["participant_name"]
        if _repo_name_freq.get(_repo_display_name, 0) > 1:
            _repo_display_name = f"{_repo_display_name}  ({_repo_disambiguator(story)})"

        # P-02 / P-05 — Deep-link highlight + scroll-to-target. Purely
        # additive: reuses the existing _target_sid capture above (no new
        # session-state, no new navigation mechanism). Only affects the
        # single story that was just auto-expanded via repo_open_story_id
        # — every other story's markup is byte-identical to before.
        #
        # NOTE: the badges/content markup below is built as CONCATENATED
        # single-line f-string literals (implicit Python string
        # concatenation — no embedded newlines or leading whitespace)
        # instead of one triple-quoted multi-line block. A triple-quoted
        # block here previously caused Streamlit's markdown renderer to
        # occasionally treat parts of the HTML as a literal/code block
        # (raw tags visible on screen) once a conditional line could
        # collapse to whitespace-only. Concatenated single-line f-strings
        # have no embedded newlines at all, so that class of bug is
        # structurally impossible here.
        _is_deep_link_target = (_target_sid == story["id"])
        _anchor_id = f"repo-target-{story['id']}"
        _content_style = (
            f"font-size:.875rem;color:{c['text_secondary']};line-height:1.7;white-space:pre-wrap;"
            f"border-radius:8px;padding:.85rem;border:1px solid {c['accent']};"
            f"border-left:3px solid {c['accent']};background:{c['accent_soft']};"
            if _is_deep_link_target else
            f"font-size:.875rem;color:{c['text_secondary']};line-height:1.7;white-space:pre-wrap;"
        )
        _deep_link_chip = (
            f'<span id="{_anchor_id}-chip" style="display:inline-flex;align-items:center;gap:.3rem;'
            f'padding:.18rem .6rem;border-radius:6px;background:{c["accent_soft"]};'
            f'color:{c["accent"]};font-size:.72rem;font-weight:600;margin-left:.5rem;">'
            f'📍 Opened from link</span>'
            if _is_deep_link_target else ""
        )

        with st.expander(
            f"{_repo_display_name} · {spec.get('label', story['format'])}"
            f"  ·  v{story.get('version', 1)}",
            expanded=(_target_sid == story["id"]),
        ):
            if _is_deep_link_target:
                # P-05 — scroll the deep-linked story into view, and clear
                # the highlight the moment the user interacts with the page
                # again. Expanders in Streamlit toggle purely on the
                # frontend (no script rerun), so a Python-side check alone
                # can never observe "the user opened a different story" —
                # this listens for the next real click anywhere on the
                # page (any expander, any button) and strips the highlight
                # styling directly, satisfying the "disappears on manual
                # interaction" requirement regardless of whether a rerun
                # happens. Fires once, then removes itself.
                st_html(
                    f"""
                    <script>
                    setTimeout(function() {{
                        var doc = window.parent.document;
                        var target = doc.getElementById("{_anchor_id}");
                        if (target) {{ target.scrollIntoView({{behavior: "smooth", block: "center"}}); }}

                        function clearHighlight() {{
                            var content = doc.getElementById("{_anchor_id}-content");
                            var chip = doc.getElementById("{_anchor_id}-chip");
                            if (content) {{
                                content.style.border = "none";
                                content.style.background = "transparent";
                                content.style.padding = "0";
                            }}
                            if (chip) {{ chip.style.display = "none"; }}
                        }}

                        doc.addEventListener("click", clearHighlight, {{ once: true, capture: true }});
                    }}, 250);
                    </script>
                    """,
                    height=0,
                )

            st.markdown(
                f'<div id="{_anchor_id}" style="display:flex;gap:.75rem;margin-bottom:.85rem;'
                f'align-items:center;flex-wrap:wrap;">'
                + status_badge(status)
                + format_badge(story['format'])
                + f'<span style="display:inline-flex;align-items:center;padding:.18rem .6rem;'
                  f'border-radius:6px;background:{c["surface_alt"]};color:{c["text_muted"]};'
                  f'font-size:.72rem;font-weight:600;border:1px solid {c["border"]};">'
                  f'v{story.get("version", 1)}</span>'
                + f'<span style="font-size:.75rem;color:{c["text_muted"]};">'
                  f'{story.get("word_count", 0)} words</span>'
                + f'<span style="font-size:.72rem;color:{c["text_muted"]};margin-left:auto;">'
                  f'{display_date(story.get("created_at"))}</span>'
                + _deep_link_chip
                + '</div>'
                + f'<div id="{_anchor_id}-content" style="{_content_style}">'
                + (content if content else '<em>No content.</em>')
                + '</div>',
                unsafe_allow_html=True,
            )

            if story.get("editor_notes"):
                st.markdown(
                    f'<div style="font-size:.78rem;color:{c["text_muted"]};'
                    f'margin-top:.65rem;font-style:italic;">'
                    f'Editor notes: {story["editor_notes"]}</div>',
                    unsafe_allow_html=True,
                )

            # ── Publishing actions — status moves ONLY through update_story_status() ──
            st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)

            if status == "approved":
                act1, _gap = st.columns([2, 5])
                with act1:
                    if st.button(
                        "📤 Mark as Published",
                        key=f"repo_pub_{story['id']}",
                        use_container_width=True,
                    ):
                        update_story_status(story["id"], "published", reviewer="editor")
                        st.success("Story marked as published.")
                        st.rerun()

            elif status == "published":
                act1, _gap = st.columns([2, 5])
                with act1:
                    if st.button(
                        "↩ Revert to Approved",
                        key=f"repo_unpub_{story['id']}",
                        use_container_width=True,
                    ):
                        update_story_status(story["id"], "approved", reviewer="editor")
                        st.info("Reverted to approved.")
                        st.rerun()

            elif status == "rejected":
                act1, _gap = st.columns([2, 5])
                with act1:
                    if st.button(
                        "↻ Return to Draft",
                        key=f"repo_draft_{story['id']}",
                        use_container_width=True,
                    ):
                        update_story_status(story["id"], "draft", reviewer="editor")
                        st.info("Returned to draft — editable again in Workspace.")
                        st.rerun()

            # ── Delete — only for statuses that haven't been formally
            # signed off yet. Approved/Published stories must be reverted
            # first, so deletion never erases something already published. ──
            if status in ("draft", "rejected", "in_review"):
                st.markdown(
                    f'<hr style="border-color:{c["border"]};margin:.75rem 0 .6rem 0;">',
                    unsafe_allow_html=True,
                )
                if st.session_state.repo_confirm_delete == story["id"]:
                    st.markdown(
                        f'<div style="font-size:.78rem;color:{c["red"]};'
                        f'font-weight:600;margin-bottom:.4rem;">'
                        f'Permanently delete this version? This cannot be undone.</div>',
                        unsafe_allow_html=True,
                    )
                    del_y, del_n, _gap2 = st.columns([2, 2, 5])
                    with del_y:
                        if st.button(
                            "Yes, delete",
                            key=f"repo_del_confirm_{story['id']}",
                            use_container_width=True,
                        ):
                            delete_story(story["id"])
                            st.session_state.repo_confirm_delete = None
                            st.success("Story deleted.")
                            st.rerun()
                    with del_n:
                        if st.button(
                            "Cancel",
                            key=f"repo_del_cancel_{story['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.repo_confirm_delete = None
                            st.rerun()
                else:
                    del_col, _gap2 = st.columns([2, 5])
                    with del_col:
                        if st.button(
                            "🗑 Delete Story",
                            key=f"repo_del_{story['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.repo_confirm_delete = story["id"]
                            st.rerun()