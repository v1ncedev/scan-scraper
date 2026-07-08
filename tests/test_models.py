"""Tests for jobalerts.models — specifically Posting.unique_key.

The most important property here isn't obvious from reading the code casually:
unique_key must ignore a URL's query string, because at least one real source
(Adzuna) embeds a session token in its URLs that changes on every API call for
the exact same job. Without this, dedup would silently break.
"""

from jobalerts.models import Posting


def test_unique_key_is_stable_for_identical_postings():
    a = Posting(source="adzuna", title="Data Analyst", company="Monzo", location="London", url="https://x/1")
    b = Posting(source="adzuna", title="Data Analyst", company="Monzo", location="London", url="https://x/1")
    assert a.unique_key == b.unique_key


def test_unique_key_ignores_case_and_surrounding_whitespace():
    a = Posting(source="adzuna", title="Data Analyst", company="Monzo", location="London", url="https://x/1")
    b = Posting(source="adzuna", title=" data analyst ", company="MONZO", location="Remote", url="https://x/1")
    assert a.unique_key == b.unique_key


def test_unique_key_differs_for_a_different_job_path():
    a = Posting(source="adzuna", title="Data Analyst", company="Monzo", location="London", url="https://x/1")
    b = Posting(source="adzuna", title="Data Analyst", company="Monzo", location="London", url="https://x/2")
    assert a.unique_key != b.unique_key


def test_unique_key_ignores_query_string_changes():
    """Regression test for the real bug found while testing against Adzuna:
    the same job's URL can carry a different session token on every request.
    """
    same_job_call_1 = Posting(
        source="adzuna",
        title="Graduate Analyst",
        company="TestCo",
        location="London",
        url="https://www.adzuna.co.uk/jobs/land/ad/12345?se=AAAA&utm_medium=api",
    )
    same_job_call_2 = Posting(
        source="adzuna",
        title="Graduate Analyst",
        company="TestCo",
        location="London",
        url="https://www.adzuna.co.uk/jobs/land/ad/12345?se=ZZZZ&utm_medium=api",
    )
    assert same_job_call_1.unique_key == same_job_call_2.unique_key


def test_unique_key_still_differs_when_the_job_path_itself_differs():
    """Sanity check: stripping the query string must not make every job look
    the same — two genuinely different jobs (different path/job id) must
    still produce different keys even if their query strings happen to match.
    """
    job_a = Posting(
        source="adzuna",
        title="Graduate Analyst",
        company="TestCo",
        location="London",
        url="https://www.adzuna.co.uk/jobs/land/ad/12345?se=SAME",
    )
    job_b = Posting(
        source="adzuna",
        title="Graduate Analyst",
        company="TestCo",
        location="London",
        url="https://www.adzuna.co.uk/jobs/land/ad/67890?se=SAME",
    )
    assert job_a.unique_key != job_b.unique_key
