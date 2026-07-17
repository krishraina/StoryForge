"""
components/sidebar.py
Uses native st.sidebar — never fights Streamlit's layout engine.
"""
import streamlit as st
from components.theme import COLORS


def render_sidebar():
    c = COLORS
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:.35rem 0 1.1rem 0;
                 border-bottom:1px solid rgba(255,255,255,0.06);
                 margin-bottom:1rem;">
                <div style="font-size:1.1rem;font-weight:800;
                     color:{c['text_primary']};letter-spacing:-0.02em;
                     display:flex;align-items:center;gap:.4rem;">
                    <span style="color:{c['accent']};">✦</span> StoryForge
                </div>
                <div style="font-size:0.7rem;color:{c['text_muted']};
                     margin-top:0.15rem;letter-spacing:.02em;">
                    IAC &nbsp;·&nbsp; Cloud Counselage
                </div>
            </div>
            <div style="font-size:0.62rem;font-weight:600;letter-spacing:.1em;
                 text-transform:uppercase;color:{c['text_muted']};
                 margin:0 0 .35rem .65rem;">
                Workspace
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.page_link("app.py",                   label="🏠  Dashboard")
        st.page_link("pages/1_Participants.py",   label="👥  Participants")
        st.page_link("pages/2_Workspace.py",      label="✍️  Workspace")
        st.page_link("pages/3_Review_Queue.py",   label="📋  Review Queue")
        st.page_link("pages/4_Repository.py",     label="📚  Repository")
        st.page_link("pages/5_Exports.py",        label="📤  Exports")
        st.page_link("pages/6_Batch_Operations.py", label="🗂  Batch Operations")

        st.markdown(
            f"""
            <div style="font-size:0.7rem;color:{c['text_muted']};
                 border-top:1px solid rgba(255,255,255,0.06);
                 margin-top:1.4rem;padding-top:.9rem;line-height:1.6;">
                <strong style="color:{c['text_secondary']};font-weight:600;">
                    AI Disclosure
                </strong><br>
                Stories generated with Gemini AI.<br>
                Human review required before publish.
            </div>
            """,
            unsafe_allow_html=True,
        )