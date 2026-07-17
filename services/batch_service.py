"""
services/batch_service.py
Phase 7 — Batch Operations
───────────────────────────
Orchestration layer for bulk participant import and bulk story
generation. Follows the same separation as the rest of the app:

    db_service      → all SQL
    gemini_service  → all AI calls
    batch_service   → sequences the two and tracks batch_jobs progress

No Streamlit imports here on purpose — this stays usable from a future
CLI script or API endpoint without dragging in the UI layer.
"""

import csv
import io
import time
from datetime import datetime

from core.config import settings
from core.constants import CONSENT_LEVELS
from services.db_service import (
    create_batch_job,
    update_batch_job,
    bulk_upsert_participants,
    email_exists,
    save_story,
    replace_latest_draft_story,
    get_stories_for_participant,
)
from services.gemini_service import generate_story


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════
# CSV IMPORT
# ══════════════════════════════════════════════════════════════════════

REQUIRED_COLUMNS = ["name"]
OPTIONAL_COLUMNS = [
    "email", "program", "domain", "background",
    "achievements", "challenges", "outcomes",
    "consent_level", "linkedin_url",
]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def parse_participant_csv(file_bytes: bytes) -> tuple:
    """
    Parses uploaded CSV bytes into normalized, validated participant
    dicts ready for bulk_upsert_participants(). Validation happens here
    — not at insert time — so the UI can show a full error report
    before anything touches the database.

    Returns (valid_rows, errors).
    errors = [{"row": line_no, "name": str, "error": str}, ...]
    line_no is 1-indexed against the file as the user would open it
    in a spreadsheet (row 1 = header).
    """
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    except Exception as exc:
        return [], [{"row": 0, "name": "—", "error": f"Could not read file: {exc}"}]

    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return [], [{"row": 0, "name": "—", "error": "CSV appears to be empty."}]

    header_map = {h.strip().lower(): h for h in reader.fieldnames if h}
    missing = [col for col in REQUIRED_COLUMNS if col not in header_map]
    if missing:
        return [], [{
            "row": 0, "name": "—",
            "error": f"Missing required column(s): {', '.join(missing)}. "
                     f"Expected headers like: {', '.join(ALL_COLUMNS)}",
        }]

    valid_rows, errors = [], []
    seen_emails_in_file = set()

    for line_no, raw in enumerate(reader, start=2):

        def get(col: str) -> str:
            key = header_map.get(col)
            return (raw.get(key, "") or "").strip() if key else ""

        name = get("name")
        if not name:
            errors.append({"row": line_no, "name": "—", "error": "Name is required."})
            continue

        consent = (get("consent_level") or "full").lower()
        if consent not in CONSENT_LEVELS:
            errors.append({
                "row": line_no, "name": name,
                "error": f"Invalid consent_level '{consent}'. Must be one of: "
                         f"{', '.join(CONSENT_LEVELS.keys())}.",
            })
            continue

        email = get("email") or None
        if email:
            if email in seen_emails_in_file:
                errors.append({
                    "row": line_no, "name": name,
                    "error": f"Duplicate email '{email}' appears more than once in this file.",
                })
                continue
            if email_exists(email):
                errors.append({
                    "row": line_no, "name": name,
                    "error": f"Email '{email}' is already registered to another participant.",
                })
                continue
            seen_emails_in_file.add(email)

        valid_rows.append({
            "name": name,
            "email": email,
            "program": get("program") or None,
            "domain": get("domain") or None,
            "background": get("background"),
            "achievements": get("achievements"),
            "challenges": get("challenges"),
            "outcomes": get("outcomes"),
            "consent_level": consent,
            "linkedin_url": get("linkedin_url") or None,
        })

    return valid_rows, errors


def import_participants(valid_rows: list) -> dict:
    """
    Runs the DB import for already-validated rows inside a batch_jobs
    record, so the run shows up on the Progress Dashboard and any
    per-row failures are kept for review rather than silently dropped.
    """
    job_id = create_batch_job("import", total_items=len(valid_rows))

    success, row_errors = bulk_upsert_participants(valid_rows, batch_id=job_id)
    fail = len(row_errors)

    update_batch_job(
        job_id,
        processed_items=len(valid_rows),
        success_count=success,
        fail_count=fail,
        status="completed" if fail == 0 else ("partial" if success else "failed"),
        summary=f"{success} imported, {fail} failed",
        detail_log="\n".join(
            f"Row {e['row']} ({e['name']}): {e['error']}" for e in row_errors
        ) or None,
        finished_at=_now(),
    )

    return {"job_id": job_id, "success": success, "errors": row_errors}


# ══════════════════════════════════════════════════════════════════════
# BULK STORY GENERATION
# ══════════════════════════════════════════════════════════════════════

def bulk_generate_stories(
    participants: list,
    formats: list,
    progress_callback=None,
    gen_mode: str = "create_new",
) -> dict:
    """
    Generates every selected format for every selected participant,
    sequentially (Gemini free-tier RPM limits make parallel calls
    unsafe). Each successful story is saved as a draft immediately —
    if the run is interrupted at item 40 of 100, the first 40 are
    already in the database, not lost.

    gen_mode controls what happens when a story already exists:
      "create_new"    — always INSERT a new version (default, matches Workspace)
      "skip_existing" — skip if any story (any status) exists for this pid+fmt
      "replace_draft" — UPDATE the latest draft in-place; INSERT if none exists

    progress_callback(participant_name, fmt, p_idx, p_total,
                       f_idx, f_total, status)
        status is one of "generating" | "success" | "skipped" | "error"

    Returns a summary dict with job_id, success_count, fail_count, log.
    """
    total_units = len(participants) * len(formats)
    job_id = create_batch_job("generate", total_items=total_units)

    success_count = 0
    fail_count = 0
    skip_count = 0
    log_lines = []
    processed = 0
    last_unit = total_units - 1

    for p_idx, participant in enumerate(participants):
        pid = participant["id"]

        # Pre-fetch existing stories once per participant to avoid N×M DB hits
        existing_stories = get_stories_for_participant(pid)
        existing_formats = {s["format"] for s in existing_stories}

        for f_idx, fmt in enumerate(formats):

            # ── Skip Existing mode ────────────────────────────────────
            if gen_mode == "skip_existing" and fmt in existing_formats:
                skip_count += 1
                processed += 1
                unit_index = p_idx * len(formats) + f_idx
                if unit_index < last_unit:
                    pass  # no Gemini call, no delay needed
                update_batch_job(
                    job_id,
                    processed_items=processed,
                    success_count=success_count,
                    fail_count=fail_count,
                )
                continue  # skip to next format

            if progress_callback:
                progress_callback(
                    participant["name"], fmt, p_idx, len(participants),
                    f_idx, len(formats), "generating",
                )

            result = generate_story(participant, fmt)

            if "content" in result:
                story_data = {
                    "id": None,
                    "participant_id": pid,
                    "format": fmt,
                    "content": result["content"],
                    "status": "draft",
                    "editor_notes": "",
                    "ai_model": "gemini-2.5-flash",
                    "generation_prompt": result.get("prompt", ""),
                    "batch_job_id": job_id,   # BT-08: marks story as batch-originated
                }

                if gen_mode == "replace_draft":
                    replace_latest_draft_story(pid, fmt, story_data)
                else:
                    # create_new — always INSERT (full version history)
                    save_story(story_data)

                success_count += 1
                unit_status = "success"
            else:
                fail_count += 1
                unit_status = "error"
                log_lines.append(
                    f"{participant['name']} / {fmt}: {result.get('error', 'Unknown error')}"
                )

            processed += 1

            if progress_callback:
                progress_callback(
                    participant["name"], fmt, p_idx, len(participants),
                    f_idx, len(formats), unit_status,
                )

            update_batch_job(
                job_id,
                processed_items=processed,
                success_count=success_count,
                fail_count=fail_count,
            )

            unit_index = p_idx * len(formats) + f_idx
            if unit_index < last_unit:
                time.sleep(settings.GEMINI_SEQUENTIAL_DELAY)

    skipped_note = f", {skip_count} skipped" if skip_count else ""
    update_batch_job(
        job_id,
        status="completed" if fail_count == 0 else ("partial" if success_count else "failed"),
        summary=f"{success_count} generated, {fail_count} failed{skipped_note}",
        detail_log="\n".join(log_lines) or None,
        finished_at=_now(),
    )

    return {
        "job_id": job_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "log": log_lines,
    }


# ══════════════════════════════════════════════════════════════════════
# F-02 — PER-UNIT SERVICE FUNCTIONS
# Called once per Streamlit rerun by 6_Batch_Operations.py.
# No Streamlit imports. No session_state. No st.rerun(). Pure service.
# ══════════════════════════════════════════════════════════════════════

def build_batch_queue(
    participants: list,
    formats: list,
    gen_mode: str,
) -> tuple:
    """
    Build a flat list of (participant_dict, fmt_str) pairs ready to be
    processed one per Streamlit rerun.

    For skip_existing mode, each participant's existing story formats are
    fetched from the DB once upfront and already-covered units are removed
    from the queue before any Gemini calls start — zero repeated DB hits
    during the work loop.

    For create_new and replace_draft modes no DB read is needed; existing
    is always an empty set and the queue contains every (participant, fmt)
    combination.

    Returns:
        queue      — list of (participant_dict, fmt_str) tuples
        skip_count — number of units excluded by skip_existing filtering
    """
    queue: list = []
    skip_count: int = 0

    for participant in participants:
        if gen_mode == "skip_existing":
            existing_formats = {
                s["format"]
                for s in get_stories_for_participant(participant["id"])
            }
        else:
            existing_formats = set()

        for fmt in formats:
            if gen_mode == "skip_existing" and fmt in existing_formats:
                skip_count += 1
            else:
                queue.append((participant, fmt))

    return queue, skip_count


def generate_next_batch_unit(
    job_id: int,
    participant: dict,
    fmt: str,
    gen_mode: str,
    existing_formats: set,
) -> dict:
    """
    Generate and persist exactly one story unit (one participant × one
    format). Pure service function — no Streamlit dependencies.

    The caller (6_Batch_Operations.py) invokes this once per rerun and is
    responsible for queue management, progress UI, cancel state, and
    calling st.rerun(). This function only does the work for a single unit.

    Args:
        job_id          : batch_jobs row ID for this run.
        participant     : participant dict (from db_service).
        fmt             : story format key — linkedin / narrative /
                          testimonial / case_study.
        gen_mode        : "create_new" | "skip_existing" | "replace_draft".
        existing_formats: set of format keys already present for this
                          participant. Pass set() when the caller has
                          pre-filtered the queue via build_batch_queue()
                          (the normal UI path). Kept as an explicit
                          parameter so non-UI callers can still use the
                          skip logic without pre-filtering.

    Returns:
        {
            "status"  : "success" | "skipped" | "error",
            "story_id": int | None,
            "message" : str,
        }
    """
    pid  = participant["id"]
    name = participant.get("name", "—")

    # Skip check — honoured even when existing_formats is supplied directly
    # by a non-UI caller (the UI path always passes set() after pre-filtering)
    if gen_mode == "skip_existing" and fmt in existing_formats:
        return {
            "status":   "skipped",
            "story_id": None,
            "message":  f"{name} / {fmt}: skipped (story already exists)",
        }

    result = generate_story(participant, fmt)

    if "content" in result:
        story_data = {
            "id":                None,
            "participant_id":    pid,
            "format":            fmt,
            "content":           result["content"],
            "status":            "draft",
            "editor_notes":      "",
            "ai_model":          "gemini-2.5-flash",
            "generation_prompt": result.get("prompt", ""),
            "batch_job_id":      job_id,   # BT-08: marks story as batch-originated
        }

        if gen_mode == "replace_draft":
            sid = replace_latest_draft_story(pid, fmt, story_data)
        else:
            # create_new (default) — always INSERT, full version history
            sid = save_story(story_data)

        return {
            "status":   "success",
            "story_id": sid,
            "message":  f"{name} / {fmt}: generated",
        }

    return {
        "status":   "error",
        "story_id": None,
        "message":  f"{name} / {fmt}: {result.get('error', 'Unknown error')}",
    }