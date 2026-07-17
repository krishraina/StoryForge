import streamlit as st
from components.theme import STATUS_COLORS, COLORS
from core.constants import STORY_FORMATS


def status_badge(status: str) -> str:
    """Return inline HTML for a status badge."""
    fg, bg = STATUS_COLORS.get(status, ("#94a3b8", "#1c2333"))
    label = status.replace("_", " ").title()
    return (
        f'<span style="'
        f'display:inline-flex;align-items:center;gap:.32rem;'
        f'padding:.19rem .62rem;border-radius:20px;'
        f'background:{bg};color:{fg};border:1px solid {fg}33;'
        f'font-size:.71rem;font-weight:600;line-height:1.5;'
        f'letter-spacing:.025em;text-transform:capitalize;">'
        f'{_status_dot(fg)}{label}</span>'
    )


def _status_dot(color: str) -> str:
    return (
        f'<span style="width:6px;height:6px;border-radius:50%;'
        f'background:{color};display:inline-block;flex-shrink:0;"></span>'
    )


def format_badge(fmt: str) -> str:
    c = COLORS
    icons = {
        "linkedin":    "💼",
        "narrative":   "📖",
        "testimonial": "💬",
        "case_study":  "📊",
    }
    icon = icons.get(fmt, "✦")
    label = fmt.replace("_", " ").title()
    return (
        f'<span style="'
        f'display:inline-flex;align-items:center;gap:.36rem;'
        f'padding:.19rem .64rem;border-radius:7px;line-height:1.5;'
        f'background:{c["surface_alt"]};color:{c["text_secondary"]};'
        f'font-size:.71rem;font-weight:500;letter-spacing:.01em;'
        f'border:1px solid rgba(255,255,255,0.07);">'
        f'{icon} {label}</span>'
    )


def word_count_indicator(count: int, target_min: int, target_max: int) -> str:
    c = COLORS
    if count < target_min:
        color = c["amber"]
        note  = f"↑ {target_min - count} words short"
    elif count > target_max:
        color = c["amber"]
        note  = f"↓ {count - target_max} words over"
    else:
        color = c["green"]
        note  = "✓ within range"

    return (
        f'<span style="font-family:\'DM Mono\',monospace;font-size:.75rem;color:{color};">'
        f'{count} words &nbsp;·&nbsp; {note}'
        f'</span>'
    )


# ══════════════════════════════════════════════════════════════════════
# FB-03 — Shared dropdown/option-building helpers
# ──────────────────────────────────────────────────────────────────────
# Pure display helpers only — no Streamlit widgets, no DB access, no
# session-state. Consolidates duplicated {id: label} construction that
# previously lived independently in Workspace, Participants, Exports,
# and Batch Operations. Callers are still responsible for building the
# actual st.selectbox / st.multiselect widgets and reading the results.
# ══════════════════════════════════════════════════════════════════════

def participant_options(participants: list) -> dict:
    """
    Build {participant_id: display_label} for dropdown/multiselect options.

    Plain name when unique across the given list; when two or more
    participants share a name, a disambiguating suffix (domain · email,
    falling back to a truncated program, falling back to #id) is appended
    so duplicate-name participants remain individually selectable by ID
    rather than colliding on display text (BT-09).
    """
    name_freq: dict = {}
    for p in participants:
        name_freq[p["name"]] = name_freq.get(p["name"], 0) + 1

    def _label(p: dict) -> str:
        name = p["name"]
        if name_freq.get(name, 1) <= 1:
            return name
        parts = []
        if p.get("domain"):
            parts.append(p["domain"])
        if p.get("email"):
            parts.append(p["email"])
        if not parts and p.get("program"):
            parts.append(p["program"][:35])
        suffix = "  ·  ".join(parts) if parts else f"#{p['id']}"
        return f"{name}  ({suffix})"

    return {p["id"]: _label(p) for p in participants}


def format_options() -> dict:
    """
    Build {format_key: "icon label"} for story-format dropdown/multiselect
    options, sourced from STORY_FORMATS — the single canonical format list.
    """
    return {k: f"{v['icon']} {v['label']}" for k, v in STORY_FORMATS.items()}