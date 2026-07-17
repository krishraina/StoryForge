"""
core/config.py
──────────────
Loads all environment variables from .env and exposes
them as a single `settings` object used across the app.
"""

import os
from dotenv import load_dotenv

# Load the .env file from the project root
load_dotenv()


class Settings:
    """
    Central configuration object.
    All other modules import from here — never from os.environ directly.
    """

    # ── Gemini AI ──────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # ── App Identity ───────────────────────────────────
    APP_TITLE: str      = os.getenv("APP_TITLE", "StoryForge")
    APP_VERSION: str    = os.getenv("APP_VERSION", "3.0")

    # ── StoryForge branding ────────────────────────────
    APP_NAME: str    = "StoryForge"
    APP_TAGLINE: str = "AI-Assisted Impact Storytelling Operations"
    ORG_NAME: str    = "Cloud Counselage · IAC"

    # ── Generation Parameters ──────────────────────────
    MAX_OUTPUT_TOKENS: int   = int(os.getenv("MAX_OUTPUT_TOKENS", 700))
    TEMPERATURE: float       = float(os.getenv("TEMPERATURE", 0.85))

    # ── Gemini Rate-limit tuning ───────────────────────
    GEMINI_RPM_LIMIT: int          = int(os.getenv("GEMINI_RPM_LIMIT", 15))
    GEMINI_RETRY_ATTEMPTS: int     = int(os.getenv("GEMINI_RETRY_ATTEMPTS", 3))
    GEMINI_RETRY_DELAY_BASE: float = float(os.getenv("GEMINI_RETRY_DELAY_BASE", 4.0))
    GEMINI_SEQUENTIAL_DELAY: float = float(os.getenv("GEMINI_SEQUENTIAL_DELAY", 2.5))

    # ── Output folders ─────────────────────────────────
    OUTPUT_DIR: str  = os.path.join(os.path.dirname(__file__), "..", "outputs")
    DB_PATH: str     = os.getenv("DB_PATH", "outputs/iac_stories.db")
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")

    def validate(self) -> tuple[bool, str]:
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY == "paste_your_key_here":
            return False, (
                "Gemini API key not found.\n"
                "Please open your .env file and paste your key next to GEMINI_API_KEY=."
            )
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        return True, "OK"


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