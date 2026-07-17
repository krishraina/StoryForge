"""
core/database.py
─────────────────
SQLite layer. Safe to run against both fresh and existing DBs —
all migrations are additive (ALTER TABLE ADD COLUMN IF NOT EXISTS pattern).
"""

import sqlite3
import os
from core.config import settings


def get_connection() -> sqlite3.Connection:
    db_path = settings.DB_PATH
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS participants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            email           TEXT UNIQUE,
            program         TEXT,
            cohort          TEXT,
            domain          TEXT,
            background      TEXT,
            achievements    TEXT,
            challenges      TEXT,
            outcomes        TEXT,
            consent_level   TEXT DEFAULT 'full',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stories (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id      INTEGER NOT NULL REFERENCES participants(id),
            format              TEXT NOT NULL,
            content             TEXT,
            word_count          INTEGER DEFAULT 0,
            status              TEXT DEFAULT 'draft',
            version             INTEGER DEFAULT 1,
            ai_model            TEXT,
            generation_prompt   TEXT,
            editor_notes        TEXT,
            reviewed_by         TEXT,
            reviewed_at         DATETIME,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id   INTEGER,
            action      TEXT,
            actor       TEXT DEFAULT 'system',
            detail      TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS batch_jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type        TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            total_items     INTEGER DEFAULT 0,
            processed_items INTEGER DEFAULT 0,
            success_count   INTEGER DEFAULT 0,
            fail_count      INTEGER DEFAULT 0,
            summary         TEXT,
            detail_log      TEXT,
            started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            finished_at     DATETIME,
            created_by      TEXT DEFAULT 'editor'
        );
    """)

    # ── Safe migrations for existing DBs ─────────────────────────────
    p_cols = {row[1] for row in c.execute("PRAGMA table_info(participants)")}
    for col, ddl in [
        ("email",         "ALTER TABLE participants ADD COLUMN email TEXT"),
        ("cohort",        "ALTER TABLE participants ADD COLUMN cohort TEXT"),
        ("domain",        "ALTER TABLE participants ADD COLUMN domain TEXT DEFAULT ''"),
        ("consent_level", "ALTER TABLE participants ADD COLUMN consent_level TEXT DEFAULT 'full'"),
        ("background",    "ALTER TABLE participants ADD COLUMN background TEXT"),
        ("achievements",  "ALTER TABLE participants ADD COLUMN achievements TEXT"),
        ("challenges",    "ALTER TABLE participants ADD COLUMN challenges TEXT"),
        ("outcomes",      "ALTER TABLE participants ADD COLUMN outcomes TEXT"),
        ("linkedin_url",  "ALTER TABLE participants ADD COLUMN linkedin_url TEXT"),
        ("import_batch_id", "ALTER TABLE participants ADD COLUMN import_batch_id INTEGER"),
    ]:
        if col not in p_cols:
            c.execute(ddl)

    s_cols = {row[1] for row in c.execute("PRAGMA table_info(stories)")}
    for col, ddl in [
        ("format",            "ALTER TABLE stories ADD COLUMN format TEXT NOT NULL DEFAULT 'linkedin'"),
        ("editor_notes",      "ALTER TABLE stories ADD COLUMN editor_notes TEXT"),
        ("reviewed_by",       "ALTER TABLE stories ADD COLUMN reviewed_by TEXT"),
        ("reviewed_at",       "ALTER TABLE stories ADD COLUMN reviewed_at DATETIME"),
        ("ai_model",          "ALTER TABLE stories ADD COLUMN ai_model TEXT"),
        ("generation_prompt", "ALTER TABLE stories ADD COLUMN generation_prompt TEXT"),
        ("word_count",        "ALTER TABLE stories ADD COLUMN word_count INTEGER DEFAULT 0"),
        ("version",           "ALTER TABLE stories ADD COLUMN version INTEGER DEFAULT 1"),
        ("assigned_reviewer", "ALTER TABLE stories ADD COLUMN assigned_reviewer TEXT"),
        ("batch_job_id",      "ALTER TABLE stories ADD COLUMN batch_job_id INTEGER"),
    ]:
        if col not in s_cols:
            c.execute(ddl)

    conn.commit()
    conn.close()