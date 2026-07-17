"""
core/config.py

Loads all environment variables from .env and exposes
them as a single `settings` object used across the app.
"""

import os
from dotenv import load_dotenv

# Load local .env (works locally)
load_dotenv()

# Streamlit is optional (available only when running Streamlit)
try:
    import streamlit as st
except ImportError:
    st = None


def _get_secret(name: str, default: str = "") -> str:
    """
    Read a setting from Streamlit Secrets first (deployment),
    then fall back to .env (local development).
    """
    if st is not None:
        try:
            return st.secrets[name]
        except Exception:
            pass
    return os.getenv(name, default)


class Settings:
    """
    Central configuration object.
    All other modules import from here.
    """

    # ──────────────────────────────────────────────
    # Gemini AI
    # ──────────────────────────────────────────────

    GEMINI_API_KEY: str = _get_secret("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = _get_secret("GEMINI_MODEL", "gemini-2.5-flash")

    # ──────────────────────────────────────────────
    # Application
    # ──────────────────────────────────────────────

    APP_TITLE: str = os.getenv("APP_TITLE", "StoryForge")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")

    APP_NAME: str = "StoryForge"
    APP_TAGLINE: str = "AI-Assisted Impact Storytelling Operations"
    ORG_NAME: str = "Cloud Counselage · IAC"

    # ──────────────────────────────────────────────
    # Generation
    # ──────────────────────────────────────────────

    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "700"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.85"))

    # ──────────────────────────────────────────────
    # Gemini Retry / Rate Limits
    # ──────────────────────────────────────────────

    GEMINI_RPM_LIMIT: int = int(os.getenv("GEMINI_RPM_LIMIT", "15"))
    GEMINI_RETRY_ATTEMPTS: int = int(
        os.getenv("GEMINI_RETRY_ATTEMPTS", "3")
    )
    GEMINI_RETRY_DELAY_BASE: float = float(
        os.getenv("GEMINI_RETRY_DELAY_BASE", "4.0")
    )
    GEMINI_SEQUENTIAL_DELAY: float = float(
        os.getenv("GEMINI_SEQUENTIAL_DELAY", "2.5")
    )

    # ──────────────────────────────────────────────
    # Storage
    # ──────────────────────────────────────────────

    OUTPUT_DIR: str = os.path.join(
        os.path.dirname(__file__),
        "..",
        "outputs",
    )

    DB_PATH: str = os.getenv(
        "DB_PATH",
        "outputs/iac_stories.db",
    )

    REPORTS_DIR: str = os.getenv(
        "REPORTS_DIR",
        "reports",
    )

    # ──────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────

    def validate(self) -> tuple[bool, str]:
        if (
            not self.GEMINI_API_KEY
            or self.GEMINI_API_KEY == "paste_your_key_here"
        ):
            return (
                False,
                "Gemini API key not found. Configure it in "
                ".env (local) or Streamlit Secrets (deployment).",
            )

        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

        return True, "OK"


# -------------------------------------------------
# Singleton
# -------------------------------------------------

settings = Settings()

# -------------------------------------------------
# Flat aliases
# -------------------------------------------------

APP_NAME = settings.APP_NAME
APP_TAGLINE = settings.APP_TAGLINE
ORG_NAME = settings.ORG_NAME

GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_MODEL = settings.GEMINI_MODEL

GEMINI_RPM_LIMIT = settings.GEMINI_RPM_LIMIT
GEMINI_RETRY_ATTEMPTS = settings.GEMINI_RETRY_ATTEMPTS
GEMINI_RETRY_DELAY_BASE = settings.GEMINI_RETRY_DELAY_BASE
GEMINI_SEQUENTIAL_DELAY = settings.GEMINI_SEQUENTIAL_DELAY

DB_PATH = settings.DB_PATH
REPORTS_DIR = settings.REPORTS_DIR