"""
StoryForge shared theme.
Call apply_theme() at the top of every page.
All CSS Fs injected once via st.markdown(unsafe_allow_html=True) in a
controlled block — never scattered across page code.
"""

import streamlit as st

# ── Palette ───────────────────────────────────────────────────────────
COLORS = {
    "bg":           "#0f1117",
    "surface":      "#161b27",
    "surface_alt":  "#1c2333",
    "border":       "#252d3d",
    "border_light": "#2e3a50",
    "text_primary": "#e8edf5",
    "text_secondary":"#8899aa",
    "text_muted":   "#55667a",
    "accent":       "#4f8ef7",
    "accent_soft":  "#1a2f52",
    "green":        "#10b981",
    "green_soft":   "#0d2b1f",
    "amber":        "#f59e0b",
    "amber_soft":   "#2a1f08",
    "red":          "#ef4444",
    "red_soft":     "#2b1010",
    "purple":       "#8b5cf6",
    "purple_soft":  "#1e1433",
}

STATUS_COLORS = {
    "draft":     ("#94a3b8", "#1c2333"),
    "in_review": ("#f59e0b", "#2a1f08"),
    "approved":  ("#10b981", "#0d2b1f"),
    "rejected":  ("#ef4444", "#2b1010"),
    "published": ("#8b5cf6", "#1e1433"),
}

FONT_URL = "https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap"


def page_config(title: str = "StoryForge", layout: str = "wide"):
    st.set_page_config(
        page_title=f"{title} · StoryForge",
        page_icon="✦",
        layout=layout,
        initial_sidebar_state="expanded",
    )


def apply_theme():
    """Inject global CSS. Call once per page after page_config()."""
    c = COLORS
    css = f"""
<style>
@import url('{FONT_URL}');

/* ── Reset & base ─────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif !important;
    background-color: {c['bg']} !important;
    color: {c['text_primary']} !important;
}}

/* ── Hide Streamlit chrome ────────────────────────────────── */
#MainMenu, footer, header {{visibility: hidden;}}
.stDeployButton {{display: none;}}
[data-testid="stToolbar"] {{display: none;}}
[data-testid="stSidebarNav"] {{display: none;}}

/* ── Main container ───────────────────────────────────────── */
.main .block-container {{
    padding: 2.25rem 3rem 4rem 3rem !important;
    max-width: 1440px !important;
}}

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {c['surface']} !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    box-shadow: 1px 0 0 rgba(0,0,0,0.18) !important;
    min-width: 248px !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 0.25rem;
}}
[data-testid="stSidebar"] .block-container {{
    padding: 1.5rem 1.1rem 1.5rem 1.1rem !important;
}}

/* Nav links (st.page_link) — rhythm, active state, quiet hover */
[data-testid="stSidebar"] [data-testid="stPageLink"] {{
    border-radius: 8px !important;
    padding: 0.5rem 0.65rem !important;
    margin-bottom: 0.1rem !important;
    font-size: 0.855rem !important;
    font-weight: 500 !important;
    color: {c['text_secondary']} !important;
    transition: background 0.12s ease, color 0.12s ease !important;
    border-left: 2px solid transparent !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover {{
    background: rgba(255,255,255,0.035) !important;
    color: {c['text_primary']} !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] p {{
    font-size: 0.855rem !important;
    font-weight: 500 !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"][aria-current="page"] {{
    background: {c['accent_soft']} !important;
    border-left: 2px solid {c['accent']} !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"][aria-current="page"] p {{
    color: {c['accent']} !important;
    font-weight: 600 !important;
}}

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {{
    background: {c['accent']} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 9px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.55rem 1.25rem !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.16) !important;
}}
.stButton > button:hover {{
    background: #6099f8 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(79,142,247,0.3) !important;
}}
.stButton > button:active {{
    transform: translateY(0px) !important;
}}

/* ── Secondary button variant ─────────────────────────────── */
.stButton > button[kind="secondary"] {{
    background: transparent !important;
    border: 1px solid {c['border_light']} !important;
    color: {c['text_secondary']} !important;
    box-shadow: none !important;
}}
.stButton > button[kind="secondary"]:hover {{
    border-color: {c['accent']} !important;
    color: {c['accent']} !important;
    box-shadow: none !important;
}}

/* ── Download button ──────────────────────────────────────── */
.stDownloadButton > button {{
    background: {c['green_soft']} !important;
    color: {c['green']} !important;
    border: 1px solid rgba(16,185,129,0.45) !important;
    border-radius: 9px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.55rem 1.25rem !important;
    transition: all 0.18s ease !important;
}}
.stDownloadButton > button:hover {{
    background: {c['green']} !important;
    color: #fff !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(16,185,129,0.25) !important;
}}

/* ── Radio buttons ────────────────────────────────────────── */
.stRadio > div {{
    gap: 0.5rem !important;
}}
.stRadio label {{
    background: {c['surface']} !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 9px !important;
    padding: 0.4rem 0.9rem !important;
    font-size: 0.875rem !important;
    color: {c['text_secondary']} !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}}
.stRadio label:has(input:checked) {{
    border-color: {c['accent']} !important;
    color: {c['accent']} !important;
    background: {c['accent_soft']} !important;
}}

/* ── Inputs ───────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div,
.stMultiSelect > div > div {{
    background-color: {c['surface_alt']} !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 9px !important;
    color: {c['text_primary']} !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {c['accent']} !important;
    box-shadow: 0 0 0 3px rgba(79,142,247,0.15) !important;
    outline: none !important;
}}

/* ── Labels ───────────────────────────────────────────────── */
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stMultiSelect label,
.stCheckbox label {{
    color: {c['text_muted']} !important;
    font-size: 0.76rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.07) !important;
    gap: 0 !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    color: {c['text_muted']} !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.65rem 1.2rem !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    transition: all 0.15s ease !important;
}}
.stTabs [aria-selected="true"] {{
    color: {c['accent']} !important;
    border-bottom-color: {c['accent']} !important;
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {c['text_primary']} !important;
    background: rgba(79,142,247,0.05) !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background: transparent !important;
    padding-top: 1.25rem !important;
}}

/* ── Progress ─────────────────────────────────────────────── */
.stProgress > div > div {{
    background-color: {c['accent']} !important;
    border-radius: 4px !important;
}}
.stProgress > div {{
    background-color: {c['border']} !important;
    border-radius: 4px !important;
}}

/* ── Alerts ───────────────────────────────────────────────── */
.stAlert {{
    border-radius: 8px !important;
    border: none !important;
}}

/* ── Divider ──────────────────────────────────────────────── */
hr {{
    border-color: rgba(255,255,255,0.055) !important;
    margin: 1.25rem 0 !important;
}}

/* ── Expanders (accordions) ─────────────────────────────────
   Default Streamlit expanders read as generic boxes. Lighten the
   shell, put weight on the header text, and let the open state feel
   like a natural extension rather than a separate stacked card. */
[data-testid="stExpander"] {{
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.055) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}}
[data-testid="stExpander"] summary {{
    padding: 0.7rem 1rem !important;
    font-size: 0.86rem !important;
    font-weight: 600 !important;
    color: {c['text_secondary']} !important;
}}
[data-testid="stExpander"] summary:hover {{
    color: {c['text_primary']} !important;
}}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    padding: 0.25rem 1rem 1rem 1rem !important;
    border-top: 1px solid rgba(255,255,255,0.045) !important;
}}

/* ── st.container(border=True) — used as ad-hoc "cards" across
   Batch Operations / Participants. Reduce border weight so they
   recede behind sf-card (which stays the dominant surface). ──── */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: rgba(255,255,255,0.05) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}}

/* ── Metric ───────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {c['surface']} !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.14) !important;
}}
[data-testid="stMetricLabel"] {{
    color: {c['text_muted']} !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
}}
[data-testid="stMetricValue"] {{
    color: {c['text_primary']} !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
}}

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['bg']}; }}
::-webkit-scrollbar-thumb {{
    background: {c['border_light']};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{ background: {c['text_muted']}; }}

/* ── Utility classes (safe, no raw text leak) ─────────────── */
.sf-card {{
    background: {c['surface']};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 1.35rem 1.5rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.16), 0 1px 1px rgba(0,0,0,0.08);
}}
.sf-card-alt {{
    background: {c['surface_alt']};
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 11px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.12);
}}
.sf-page-title {{
    font-size: 1.45rem;
    font-weight: 700;
    color: {c['text_primary']};
    letter-spacing: -0.025em;
    line-height: 1.25;
    margin: 0 0 0.35rem 0;
}}
.sf-page-subtitle {{
    font-size: 0.85rem;
    font-weight: 400;
    color: {c['text_muted']};
    letter-spacing: 0.002em;
    margin: 0;
}}
.sf-section-label {{
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.11em;
    text-transform: uppercase;
    color: {c['text_muted']};
    margin-bottom: 0.85rem;
}}
.sf-word-count {{
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: {c['text_muted']};
}}
.sf-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.19rem 0.62rem;
    border-radius: 20px;
    font-size: 0.71rem;
    font-weight: 600;
    letter-spacing: 0.025em;
    text-transform: capitalize;
    line-height: 1.5;
}}
.sf-disclosure {{
    background: {c['surface_alt']};
    border: 1px solid rgba(255,255,255,0.05);
    border-left: 3px solid {c['accent']};
    border-radius: 0 9px 9px 0;
    padding: 0.75rem 1rem;
    font-size: 0.8rem;
    color: {c['text_muted']};
    font-style: italic;
    line-height: 1.65;
}}
.sf-consent-ok {{
    background: {c['green_soft']};
    border: 1px solid rgba(16,185,129,0.35);
    border-radius: 9px;
    padding: 0.6rem 0.9rem;
    font-size: 0.82rem;
    color: {c['green']};
}}
.sf-consent-warn {{
    background: {c['red_soft']};
    border: 1px solid rgba(239,68,68,0.35);
    border-radius: 9px;
    padding: 0.6rem 0.9rem;
    font-size: 0.82rem;
    color: {c['red']};
}}
.sf-generation-status {{
    background: {c['surface_alt']};
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 9px;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: {c['text_secondary']};
    line-height: 1.6;
}}

/* ── Metric hierarchy ─────────────────────────────────────────
   One hero metric (the number that matters most on a given page)
   vs. quiet secondary metrics beside it — replaces "N identical
   boxes in a row." No border on secondaries; a hairline divider
   between them instead, so the group reads as one strip, not N
   separate cards. */
.sf-metric-strip {{
    display: flex;
    align-items: stretch;
    background: {c['surface']};
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 14px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.16);
    overflow: hidden;
}}
.sf-metric-hero {{
    flex: 1.3;
    padding: 1.1rem 1.5rem;
    border-right: 1px solid rgba(255,255,255,0.06);
}}
.sf-metric-hero .sf-metric-value {{
    font-family: 'DM Mono', monospace;
    font-size: 2.1rem;
    font-weight: 700;
    line-height: 1.1;
    color: {c['text_primary']};
    letter-spacing: -0.02em;
}}
.sf-metric-cell {{
    flex: 1;
    padding: 1.1rem 1.35rem;
    border-right: 1px solid rgba(255,255,255,0.045);
    display: flex;
    flex-direction: column;
    justify-content: center;
}}
.sf-metric-cell:last-child {{ border-right: none; }}
.sf-metric-cell .sf-metric-value {{
    font-family: 'DM Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
    line-height: 1.1;
}}
.sf-metric-label {{
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: {c['text_muted']};
    margin-top: 0.3rem;
}}

/* ── Unified toolbar (search + filters as one instrument) ───── */
.sf-toolbar-wrap [data-testid="column"] {{
    padding: 0 !important;
}}
.sf-toolbar-wrap {{
    background: {c['surface']};
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 10px;
    padding: 0.3rem 0.6rem;
    margin-bottom: 0.25rem;
}}
.sf-toolbar-wrap .stTextInput > div > div > input,
.sf-toolbar-wrap .stSelectbox > div > div {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* ── Operations / list rows — a dominant label + quiet metadata,
   instead of a bordered rectangle with equal-weight text. ─────── */
.sf-op-row {{
    display: flex;
    align-items: center;
    gap: 0.9rem;
    padding: 0.85rem 0.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.045);
}}
.sf-op-row:last-child {{ border-bottom: none; }}
.sf-op-title {{
    font-size: 0.92rem;
    font-weight: 600;
    color: {c['text_primary']};
}}
.sf-op-desc {{
    font-size: 0.76rem;
    color: {c['text_muted']};
    margin-top: 0.1rem;
}}

/* ── Activity timeline ────────────────────────────────────────
   Left rail with connecting line + dot, so "Recent Activity" reads
   as a sequence rather than another stack of cards. ─────────────── */
.sf-timeline {{ position: relative; padding-left: 1.15rem; }}
.sf-timeline::before {{
    content: "";
    position: absolute;
    left: 4px; top: 6px; bottom: 6px;
    width: 1px;
    background: rgba(255,255,255,0.08);
}}
.sf-timeline-item {{
    position: relative;
    padding-bottom: 1.15rem;
}}
.sf-timeline-item:last-child {{ padding-bottom: 0; }}
.sf-timeline-item::before {{
    content: "";
    position: absolute;
    left: -1.15rem; top: 5px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: {c['accent']};
    box-shadow: 0 0 0 3px {c['accent_soft']};
}}

/* ── Ghost button — quiet secondary action, no card wrapper ─── */
.sf-list-row {{
    display: flex;
    align-items: center;
    padding: 0.65rem 0.15rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}
.sf-list-row:last-child {{ border-bottom: none; }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def status_badge_html(status: str) -> str:
    """Return a safe HTML badge string for a story status."""
    colors = STATUS_COLORS.get(status, ("#94a3b8", "#1c2333"))
    label = status.replace("_", " ").title()
    return (
        f'<span class="sf-badge" '
        f'style="color:{colors[0]};background:{colors[1]};'
        f'border:1px solid {colors[0]}33;">'
        f'{label}</span>'
    )