"""
core/timeutils.py
──────────────────
WS-01 fix: SQLite stores every CURRENT_TIMESTAMP value in UTC. Any page
that displayed created_at / started_at / finished_at by just splitting
the raw string ("2026-06-20 19:05:00" → "2026-06-20") was actually
showing the UTC calendar date — which rolls over ~5.5 hours before IST
midnight. A story saved at 12:15 AM IST on the 21st is 18:45 UTC on the
20th, so Repository showed "20 June" for something created "21 June".

Fix: convert to IST before formatting, in one shared place, instead of
re-deriving date strings ad hoc on every page.
"""

from datetime import datetime, timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist(ts_str: str):
    """Parse a 'YYYY-MM-DD HH:MM:SS' UTC string from SQLite and return it as IST. None if unparseable."""
    if not ts_str:
        return None
    ts_str = str(ts_str).split(".")[0]  # drop microseconds if present
    try:
        dt_utc = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt_utc + IST_OFFSET


def display_date(ts_str: str) -> str:
    """e.g. '21 Jun 2026' — for Repository / card date stamps."""
    dt = to_ist(ts_str)
    return dt.strftime("%d %b %Y") if dt else "—"


def display_datetime(ts_str: str) -> str:
    """e.g. '21 Jun 2026, 18:42 IST' — for Jobs / audit-trail displays."""
    dt = to_ist(ts_str)
    return dt.strftime("%d %b %Y, %H:%M") + " IST" if dt else "—"