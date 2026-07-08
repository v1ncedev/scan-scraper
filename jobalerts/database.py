"""Deduplication store: remembers which postings we've already alerted on.

We use SQLite (via Python's built-in ``sqlite3`` module — no extra dependency)
because it's a single file, needs no server, and is more than fast enough for
a job list that's at most a few thousand rows. That file is what GitHub
Actions commits back to the repo after each run so the "have we seen this
before?" state survives between ephemeral runner instances.

The whole table has one job: map a Posting's `unique_key` to "yes, we've seen
this one". Everything else (title, company, ...) is stored alongside it only
so a human can open the .db file and understand what's in there — the
pipeline itself only ever looks at `unique_key`.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from jobalerts.models import Posting

# Creates the table on first use; safe to run every time the app starts.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    unique_key    TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    company       TEXT NOT NULL,
    location      TEXT NOT NULL,
    url           TEXT NOT NULL,
    source        TEXT NOT NULL,
    first_seen_at TEXT NOT NULL
)
"""


def init_db(path: str | Path = "data/seen_jobs.db") -> sqlite3.Connection:
    """Open (creating if necessary) the SQLite database and ensure the table exists.

    Creates the parent directory too, since a fresh clone of the repo won't
    have a `data/` folder until the very first run makes one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def is_first_run(conn: sqlite3.Connection) -> bool:
    """True if the seen_jobs table is empty — i.e. we've never run before.

    Used by the pipeline to seed the database silently on the very first run
    instead of blasting a notification for every job that has ever existed.
    """
    row = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
    count = row[0]
    return count == 0


def filter_new(conn: sqlite3.Connection, postings: List[Posting]) -> List[Posting]:
    """Return only the postings whose unique_key is NOT already in the database.

    This also de-duplicates *within* the batch itself: if the same job somehow
    appears twice in one fetch (e.g. matched by two different keywords), it's
    only kept once, using the first occurrence.
    """
    new_postings: List[Posting] = []
    seen_in_this_batch = set()

    for posting in postings:
        key = posting.unique_key

        if key in seen_in_this_batch:
            continue  # duplicate within this same run's results

        row = conn.execute(
            "SELECT 1 FROM seen_jobs WHERE unique_key = ?", (key,)
        ).fetchone()
        if row is not None:
            continue  # already recorded from a previous run

        new_postings.append(posting)
        seen_in_this_batch.add(key)

    return new_postings


def mark_seen(conn: sqlite3.Connection, postings: List[Posting]) -> None:
    """Record each posting as seen, so future runs won't treat it as new.

    Uses INSERT OR IGNORE so calling this twice with the same posting (e.g. if
    it somehow slipped through filter_new twice) never raises a primary-key
    conflict — it just leaves the existing row untouched.
    """
    now = datetime.now(timezone.utc).isoformat()

    conn.executemany(
        """
        INSERT OR IGNORE INTO seen_jobs
            (unique_key, title, company, location, url, source, first_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (p.unique_key, p.title, p.company, p.location, p.url, p.source, now)
            for p in postings
        ],
    )
    conn.commit()
