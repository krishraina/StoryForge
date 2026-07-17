"""
core/config.py
──────────────
Loads all environment variables from .env and exposes
them as a single `settings` object used across the app.
"""

import os
from dotenv import load_dotenv

try:
    import streamlit as st
except ImportError:
    st = None

load_dotenv()

class Settings:
    """
    Central configuration object.
    All other modules import from here — never from os.environ directly.
    """

class Settings:
    """
    Central configuration object.
    All other modules import from here — never from os.environ directly.
    """

    # ── Gemini AI ──────────────────────────────────────
    try:
        GEMINI_API_KEY: str = st.secrets["GEMINI_API_KEY"]
    except Exception:
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # ── App Identity ───────────────────────────────────
    APP_TITLE: str = os.getenv("APP_TITLE", "StoryForge")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")

    # ── StoryForge branding ────────────────────────────
    APP_NAME: str = "StoryForge"
    APP_TAGLINE: str = "AI-Assisted Impact Storytelling Operations"
    ORG_NAME: str = "Cloud Counselage · IAC"

# Single instance — old modules use this
settings = Settings()

# Flat aliases — new StoryForge modules use these
APP_NAME    = settings.APP_NAME
APP_TAGLINE = settings.APP_TAGLINE
ORG_NAME    = settings.ORG_NAME

GEMINI_API_KEY          = settings.GEMINI_API_KEY
GEMINI_MODEL            = settings.GEMINI_MODEL
GEMINI_RPM_LIMIT        = settings.GEMINI_RPM_LIMIT
GEMINI_RETRY_ATTEMPTS   = settings.GEMINI_RETRY_ATTEMPTS
GEMINI_RETRY_DELAY_BASE = settings.GEMINI_RETRY_DELAY_BASE
GEMINI_SEQUENTIAL_DELAY = settings.GEMINI_SEQUENTIAL_DELAY

DB_PATH     = settings.DB_PATH
REPORTS_DIR = settings.REPORTS_DIR