"""Tests for jobalerts.database — the deduplication store.

Each test gets its own temporary database file (via pytest's built-in
``tmp_path`` fixture) so tests never interfere with each other or with the
real data/seen_jobs.db used by the actual tool.
"""

from jobalerts.database import filter_new, init_db, is_first_run, mark_seen
from jobalerts.models import Posting


def make_posting(suffix: str = "1") -> Posting:
    """Small helper to build a distinct Posting for each test case."""
    return Posting(
        source="adzuna",
        title=f"Graduate Analyst {suffix}",
        company="TestCo",
        location="London",
        url=f"https://example.com/job/{suffix}",
    )


def test_first_run_is_true_on_empty_database(tmp_path):
    conn = init_db(tmp_path / "test.db")
    assert is_first_run(conn) is True


def test_first_run_is_false_after_marking_seen(tmp_path):
    conn = init_db(tmp_path / "test.db")
    mark_seen(conn, [make_posting()])
    assert is_first_run(conn) is False


def test_filter_new_keeps_everything_when_database_is_empty(tmp_path):
    conn = init_db(tmp_path / "test.db")
    postings = [make_posting("1"), make_posting("2")]

    new = filter_new(conn, postings)

    assert new == postings


def test_filter_new_excludes_already_marked_postings(tmp_path):
    conn = init_db(tmp_path / "test.db")
    already_seen = make_posting("1")
    brand_new = make_posting("2")

    mark_seen(conn, [already_seen])
    new = filter_new(conn, [already_seen, brand_new])

    assert new == [brand_new]


def test_filter_new_deduplicates_within_the_same_batch(tmp_path):
    """The exact same posting appearing twice in one fetch (e.g. matched by two
    different keywords) should only be kept once."""
    conn = init_db(tmp_path / "test.db")
    duplicate = make_posting("1")

    new = filter_new(conn, [duplicate, duplicate])

    assert new == [duplicate]


def test_mark_seen_is_idempotent(tmp_path):
    """Marking the same posting seen twice must not raise a primary-key error."""
    conn = init_db(tmp_path / "test.db")
    posting = make_posting("1")

    mark_seen(conn, [posting])
    mark_seen(conn, [posting])  # should not raise

    row = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
    assert row[0] == 1


def test_full_cycle_second_run_reports_zero_new(tmp_path):
    """Simulates two pipeline runs against the same on-disk database file."""
    db_path = tmp_path / "test.db"
    postings = [make_posting("1"), make_posting("2")]

    # --- Run 1: first run, seed silently ---
    conn = init_db(db_path)
    assert is_first_run(conn) is True
    mark_seen(conn, filter_new(conn, postings))
    conn.close()

    # --- Run 2: same postings fetched again, nothing should look new ---
    conn = init_db(db_path)
    assert is_first_run(conn) is False
    new = filter_new(conn, postings)
    assert new == []
