"""
services/db_service.py
──────────────────────
Every save_story() call INSERTs a new row — full version history is kept.
version is auto-computed as (count of existing stories for that
participant+format) + 1, so first save = v1, second = v2, etc.
"""

import sqlite3

from core.database import get_connection

# ── Process-lifetime guard for stale batch-job reconciliation (BT-13) ──
# core/database.py (and therefore this module) is imported exactly once
# per Streamlit server process — Streamlit reruns re-execute page
# scripts, not module imports. This flag persists across every rerun
# within that process, so the stale-job sweep in
# mark_stale_running_jobs_failed() runs once at process startup (when
# it's actually needed, to clean up jobs orphaned by a previous crashed
# process) and is a no-op for every subsequent rerun — including the
# many reruns that fire mid-generation while a job is legitimately
# status='running'.
_stale_jobs_reconciled = False


# ── Participants ──────────────────────────────────────────────────────

def get_all_participants():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM participants ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_participant(pid: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM participants WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_participant(data: dict) -> int:
    conn = get_connection()
    try:
        pid = data.get("id")
        payload = {**data, "import_batch_id": data.get("import_batch_id")}
        if pid:
            conn.execute("""
                UPDATE participants SET
                    name=:name, email=:email, program=:program, domain=:domain,
                    background=:background, achievements=:achievements,
                    challenges=:challenges, outcomes=:outcomes,
                    consent_level=:consent_level, linkedin_url=:linkedin_url,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=:id
            """, payload)
        else:
            cur = conn.execute("""
                INSERT INTO participants
                    (name, email, program, domain, background,
                     achievements, challenges, outcomes, consent_level,
                     linkedin_url, import_batch_id)
                VALUES
                    (:name, :email, :program, :domain, :background,
                     :achievements, :challenges, :outcomes, :consent_level,
                     :linkedin_url, :import_batch_id)
            """, payload)
            pid = cur.lastrowid
        conn.commit()
        return pid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_participant(pid: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM stories WHERE participant_id=?", (pid,))
        conn.execute("DELETE FROM participants WHERE id=?", (pid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def email_exists(email: str, exclude_pid: int = None) -> bool:
    """
    Returns True if the given email is already in use by another participant.
    Pass exclude_pid when editing an existing participant so their own email
    doesn't trigger a false conflict.
    """
    if not email or not email.strip():
        return False
    conn = get_connection()
    try:
        if exclude_pid:
            row = conn.execute(
                "SELECT id FROM participants WHERE email=? AND id!=?",
                (email.strip(), exclude_pid),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM participants WHERE email=?",
                (email.strip(),),
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def bulk_upsert_participants(rows: list, batch_id: int = None) -> tuple:
    """
    Inserts a list of already-validated participant dicts one at a time.
    A failure on one row (e.g. a race-condition duplicate email) is
    recorded and skipped rather than aborting the whole batch — bulk
    imports of 100+ rows should never die because of one bad row.

    Returns (success_count, errors) where errors is a list of
    {"row": int, "name": str, "error": str} dicts, 1-indexed to match
    the CSV preview the user saw.
    """
    success = 0
    errors = []
    for i, row in enumerate(rows, start=1):
        try:
            payload = dict(row)
            if batch_id is not None:
                payload["import_batch_id"] = batch_id
            upsert_participant(payload)
            success += 1
        except sqlite3.IntegrityError:
            errors.append({
                "row": i, "name": row.get("name", "—"),
                "error": f"Email '{row.get('email')}' is already registered.",
            })
        except Exception as exc:
            errors.append({"row": i, "name": row.get("name", "—"), "error": str(exc)})
    return success, errors


# ── Stories ───────────────────────────────────────────────────────────

def get_stories_for_participant(pid: int):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT s.*, p.name AS participant_name, p.program,
                   p.domain, p.consent_level, p.import_batch_id
            FROM stories s
            JOIN participants p ON p.id = s.participant_id
            WHERE s.participant_id=?
            ORDER BY s.version DESC, s.created_at DESC
        """, (pid,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_story(sid: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _next_version(conn, pid: int, fmt: str) -> int:
    """Return the next version number for a participant+format combination."""
    row = conn.execute(
        "SELECT COUNT(*) FROM stories WHERE participant_id=? AND format=?",
        (pid, fmt),
    ).fetchone()
    return (row[0] or 0) + 1


def save_story(data: dict) -> int:
    """
    Always inserts a new story row (full version history).
    The 'id' key in data is ignored — every call creates a new version.
    version is auto-computed as next sequential number for this
    participant+format combination.
    """
    conn = get_connection()
    try:
        pid = data.get("participant_id")
        fmt = data.get("format")
        word_count = len(data.get("content", "").split()) if data.get("content") else 0
        version = _next_version(conn, pid, fmt)

        cur = conn.execute("""
            INSERT INTO stories
                (participant_id, format, content, word_count, status,
                 ai_model, generation_prompt, editor_notes, version, batch_job_id)
            VALUES
                (:participant_id, :format, :content, :word_count, :status,
                 :ai_model, :generation_prompt, :editor_notes, :version, :batch_job_id)
        """, {**data, "word_count": word_count, "version": version,
              "batch_job_id": data.get("batch_job_id")})
        sid = cur.lastrowid
        conn.commit()
        return sid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_story_status(sid: int, status: str, reviewer: str = "editor"):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE stories SET status=?, reviewed_by=?,
            reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (status, reviewer, sid))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bulk_update_story_status(story_ids: list, status: str, reviewer: str = "editor") -> int:
    """
    Applies one status transition to many stories at once — used by the
    Review Queue's bulk approve/reject bar. Returns the number updated.
    """
    if not story_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in story_ids)
        conn.execute(f"""
            UPDATE stories SET status=?, reviewed_by=?,
            reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """, (status, reviewer, *story_ids))
        conn.commit()
        return len(story_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bulk_assign_reviewer(story_ids: list, reviewer: str) -> int:
    """Assigns a reviewer name to many stories without changing status."""
    if not story_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in story_ids)
        conn.execute(f"""
            UPDATE stories SET assigned_reviewer=?, updated_at=CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """, (reviewer, *story_ids))
        conn.commit()
        return len(story_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_story(sid: int):
    """Permanently delete a single story row (one version, not the whole participant)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM stories WHERE id=?", (sid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_stories_by_status(status: str):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT s.*, p.name AS participant_name, p.program,
                   p.domain, p.consent_level, p.import_batch_id
            FROM stories s
            JOIN participants p ON p.id = s.participant_id
            WHERE s.status=?
            ORDER BY s.updated_at DESC
        """, (status,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_stories():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT s.*, p.name AS participant_name, p.program,
                   p.domain, p.consent_level, p.import_batch_id
            FROM stories s
            JOIN participants p ON p.id = s.participant_id
            ORDER BY s.updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Dashboard stats ───────────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    conn = get_connection()
    try:
        stats = {}
        stats["total_participants"] = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
        stats["total_stories"]      = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        for s in ("draft", "in_review", "approved", "published", "rejected"):
            stats[f"stories_{s}"] = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE status=?", (s,)
            ).fetchone()[0]
        # Batch job counts — used by the Dashboard nav card
        stats["batch_jobs_total"] = conn.execute(
            "SELECT COUNT(*) FROM batch_jobs"
        ).fetchone()[0]
        stats["batch_jobs_running"] = conn.execute(
            "SELECT COUNT(*) FROM batch_jobs WHERE status='running'"
        ).fetchone()[0]
        return stats
    finally:
        conn.close()


# ── Batch Jobs (Phase 7) ────────────────────────────────────────────
#
# Every CSV import and every bulk generation run gets one batch_jobs
# row that's updated as it progresses. This is the single source the
# Batch Dashboard reads from — no other page writes to this table.

def create_batch_job(job_type: str, total_items: int) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO batch_jobs (job_type, status, total_items) VALUES (?, 'running', ?)",
            (job_type, total_items),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


_BATCH_JOB_FIELDS = {
    "processed_items", "success_count", "fail_count",
    "status", "summary", "detail_log", "finished_at",
}


def update_batch_job(job_id: int, **fields) -> None:
    """Partial update — pass only the columns that changed."""
    updates = {k: v for k, v in fields.items() if k in _BATCH_JOB_FIELDS}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["id"] = job_id
    conn = get_connection()
    try:
        conn.execute(f"UPDATE batch_jobs SET {set_clause} WHERE id=:id", updates)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_batch_job(job_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM batch_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_batch_jobs(limit: int = 25):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM batch_jobs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_generate_job():
    """
    Returns the most recent batch_job row with job_type='generate', or None.
    Used by the Generate tab to reconcile st.session_state.bo_running against
    the actual DB status — so a failed/completed job always unlocks the UI
    even after a page reload or server restart.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM batch_jobs WHERE job_type='generate' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def mark_stale_running_jobs_failed() -> int:
    """
    Any batch_job still stuck in status='running' from a PREVIOUS
    server session is definitionally stale — the process that owned it
    is dead. Mark them all as failed so the Generate tab never gets
    locked by a ghost job.

    BT-13 fix — process-lifetime guard:
    This function is called at module top-level in
    6_Batch_Operations.py on EVERY Streamlit rerun, not just once at
    process boot. Streamlit reruns re-execute the page script, not the
    module import — so a plain module-level flag (_stale_jobs_reconciled,
    defined at the top of this file) persists for the lifetime of the
    server process and survives every rerun.

    Without this guard, the sweep would fire on every rerun of an
    active batch-generation loop (Phase B calls st.rerun() once per
    unit) and would repeatedly mark the CURRENTLY RUNNING job as
    'failed' — because Phase B never touches the status column, so the
    job legitimately sits at status='running' for its entire duration.
    That premature 'failed' status then short-circuits the Generate
    tab's reconciliation logic before Phase C ever gets to write the
    real, correct terminal status ('completed'/'partial'/'failed').

    With the guard: the sweep runs exactly once per process — the first
    time this function is called after the server starts — and cleans
    up any job genuinely orphaned by a previous crashed process. Every
    subsequent call in that same process (including every mid-run
    rerun) is a cheap no-op that touches the database. A fresh process
    (redeploy, crash restart) re-imports this module, the flag resets
    to False, and the one-time sweep correctly re-arms for that process.

    Returns the number of rows updated (0 on every call after the first
    in this process's lifetime).
    """
    global _stale_jobs_reconciled
    if _stale_jobs_reconciled:
        return 0
    # Mark that this process has already attempted reconciliation
    _stale_jobs_reconciled = True

    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE batch_jobs SET status='failed', "
            "summary='auto-marked failed: stale running job', "
            "finished_at=CURRENT_TIMESTAMP "
            "WHERE status='running'"
        )
        conn.commit()
        _stale_jobs_reconciled = True
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_latest_draft_story(participant_id: int, fmt: str, data: dict) -> int:
    """
    Used by gen_mode='replace_draft': finds the most recent draft for
    this participant+format and updates its content in-place instead of
    inserting a new version row.  Falls back to INSERT if no draft exists.
    Returns the story id that was written.
    """
    conn = get_connection()
    existing_draft_id = None
    try:
        row = conn.execute(
            """SELECT id FROM stories
               WHERE participant_id=? AND format=? AND status='draft'
               ORDER BY version DESC LIMIT 1""",
            (participant_id, fmt),
        ).fetchone()

        if row:
            existing_draft_id = row[0]
            word_count = len(data.get("content", "").split()) if data.get("content") else 0
            conn.execute(
                """UPDATE stories SET content=?, word_count=?, ai_model=?,
                   generation_prompt=?, editor_notes=?, batch_job_id=?,
                   updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    data.get("content", ""),
                    word_count,
                    data.get("ai_model", ""),
                    data.get("generation_prompt", ""),
                    data.get("editor_notes", ""),
                    data.get("batch_job_id"),
                    existing_draft_id,
                ),
            )
            conn.commit()
        # If no draft was found, existing_draft_id stays None — nothing
        # to commit here, the INSERT fallback happens after this
        # connection is closed (see below).
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # No draft existed — fall back to a normal INSERT via save_story(),
    # which opens and manages its own connection. This runs strictly
    # after this function's connection is closed above, so there is
    # exactly one close() call on each connection — no double-close.
    if existing_draft_id is None:
        return save_story(data)

    return existing_draft_id


def list_import_batches():
    """
    Returns completed/partial import jobs that actually have a real
    label worth showing in the Exports cohort filter — used so a user
    can export "everyone from last Tuesday's CSV" in one click.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM batch_jobs
            WHERE job_type='import' AND success_count > 0
            ORDER BY started_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_participants_by_batch_id(batch_id: int) -> list:
    """Return all participants imported in a specific batch job."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM participants WHERE import_batch_id=? ORDER BY name ASC",
            (batch_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_draft_stories_created_after(participant_ids: list, formats: list, after_ts: str) -> list:
    """
    Returns draft stories for the given participant IDs and formats
    created after a given timestamp string (ISO format).
    Used by the post-generation Submit to Review panel to scope
    the checkbox list to only the stories just created in this run.
    """
    if not participant_ids or not formats:
        return []
    conn = get_connection()
    try:
        p_placeholders = ",".join("?" for _ in participant_ids)
        f_placeholders = ",".join("?" for _ in formats)
        rows = conn.execute(
            f"""
            SELECT s.*, p.name AS participant_name
            FROM stories s
            JOIN participants p ON p.id = s.participant_id
            WHERE s.participant_id IN ({p_placeholders})
              AND s.format IN ({f_placeholders})
              AND s.status = 'draft'
              AND s.created_at >= ?
            ORDER BY p.name ASC, s.format ASC
            """,
            (*participant_ids, *formats, after_ts),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_stories_for_batch(batch_id: int) -> int:
    """Count all stories belonging to participants imported in a given batch."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT COUNT(*) FROM stories
               WHERE participant_id IN (
                   SELECT id FROM participants WHERE import_batch_id=?
               )""",
            (batch_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def count_stories_for_generate_job(job_id: int) -> int:
    """
    BT-16: Count stories actually persisted (any status) against a
    specific bulk-GENERATE batch_jobs.id — i.e. stories.batch_job_id,
    set by save_story()/replace_latest_draft_story() at the moment a
    unit succeeds inside generate_next_batch_unit().

    Distinct from count_stories_for_batch(), which is import_batch_id
    -scoped ("stories belonging to participants from an IMPORT run").
    This is generate_job-scoped ("stories actually written by THIS
    generation run"), read back from the database — the single source
    of truth per the product constitution — rather than trusted from
    in-memory session-state bookkeeping.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE batch_job_id=?",
            (job_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_story_counts_for_batch(batch_id: int) -> dict:
    """
    Returns {status: count} for all stories belonging to participants in
    the given import batch.  Used by the delete confirmation panel to give
    editors a full editorial breakdown before committing to deletion.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT status, COUNT(*) AS cnt FROM stories
               WHERE participant_id IN (
                   SELECT id FROM participants WHERE import_batch_id=?
               )
               GROUP BY status""",
            (batch_id,),
        ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}
    finally:
        conn.close()


def delete_import_batch(batch_id: int) -> dict:
    """
    Permanently deletes an import batch and everything that belongs to it:
      stories → participants → batch_job row.
    All three deletes run in a single transaction — either all succeed or
    all roll back.

    Returns {"participants_deleted": int, "stories_deleted": int}.
    """
    conn = get_connection()
    try:
        p_count = conn.execute(
            "SELECT COUNT(*) FROM participants WHERE import_batch_id=?",
            (batch_id,),
        ).fetchone()[0]

        s_count = conn.execute(
            """SELECT COUNT(*) FROM stories
               WHERE participant_id IN (
                   SELECT id FROM participants WHERE import_batch_id=?
               )""",
            (batch_id,),
        ).fetchone()[0]

        # 1. Delete stories first (foreign-key order)
        conn.execute(
            """DELETE FROM stories
               WHERE participant_id IN (
                   SELECT id FROM participants WHERE import_batch_id=?
               )""",
            (batch_id,),
        )
        # 2. Delete participants
        conn.execute(
            "DELETE FROM participants WHERE import_batch_id=?",
            (batch_id,),
        )
        # 3. Delete the batch_job record — the AND job_type='import' guard
        #    ensures a generation job can never be accidentally removed here,
        #    even if a wrong batch_id is supplied by a caller.
        conn.execute(
            "DELETE FROM batch_jobs WHERE id=? AND job_type='import'",
            (batch_id,),
        )

        conn.commit()
        return {"participants_deleted": p_count, "stories_deleted": s_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_stories_for_batch(batch_id: int) -> list:
    """
    F-06: Returns all stories (any status) belonging to participants
    imported in a given batch, joined with participant name — used by
    Batch Operations' per-batch operational summary and detail view.

    Distinct from get_batch_draft_stories() (which is batch_job_id-scoped,
    i.e. "stories generated by a batch GENERATE run") — this is
    import_batch_id-scoped, i.e. "stories belonging to participants from
    a batch IMPORT run", regardless of whether those stories were
    generated individually in Workspace or in bulk.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.*, p.name AS participant_name, p.program, p.domain
            FROM stories s
            JOIN participants p ON p.id = s.participant_id
            WHERE p.import_batch_id = ?
            ORDER BY p.name ASC, s.format ASC
            """,
            (batch_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_batch_draft_stories(participant_id: int = None) -> list:
    """
    BT-08: Returns all batch-generated draft stories
    (batch_job_id IS NOT NULL AND status = 'draft').

    Optionally filtered to a single participant_id.

    This is the permanent Editorial Inbox query — it is
    DB-sourced, so it survives page reloads, new generation
    runs, and server restarts. Workspace stories (batch_job_id
    IS NULL) are never returned here.
    """
    conn = get_connection()
    try:
        if participant_id is not None:
            rows = conn.execute(
                """
                SELECT s.*, p.name AS participant_name, p.program,
                       p.domain, p.consent_level, p.import_batch_id
                FROM stories s
                JOIN participants p ON p.id = s.participant_id
                WHERE s.batch_job_id IS NOT NULL
                  AND s.status = 'draft'
                  AND s.participant_id = ?
                ORDER BY p.name ASC, s.format ASC
                """,
                (participant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT s.*, p.name AS participant_name, p.program,
                       p.domain, p.consent_level, p.import_batch_id
                FROM stories s
                JOIN participants p ON p.id = s.participant_id
                WHERE s.batch_job_id IS NOT NULL
                  AND s.status = 'draft'
                ORDER BY p.name ASC, s.format ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()