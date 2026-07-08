"""Tests for jobalerts.sources.adzuna._format_salary.

Adzuna's raw salary fields are messier than they look — sometimes a real
employer-stated range, sometimes a single predicted figure with irrelevant
decimal precision, sometimes missing entirely. This is the logic that turns
that mess into one clean, honest display string (or None).
"""

from jobalerts.sources.adzuna import _format_salary


def test_no_salary_data_returns_none():
    assert _format_salary({}) is None
    assert _format_salary({"salary_min": 0, "salary_max": 0}) is None


def test_employer_stated_range_is_formatted_with_thousands_separator():
    result = _format_salary({"salary_min": 18000, "salary_max": 22000, "salary_is_predicted": "0"})
    assert result == "£18,000 - £22,000"


def test_predicted_single_value_is_rounded_and_labelled_estimated():
    # Adzuna's own ML prediction often has irrelevant decimal precision, and
    # min == max in this case (it's one guessed figure, not a real range).
    result = _format_salary({"salary_min": 28155.81, "salary_max": 28155.81, "salary_is_predicted": "1"})
    assert result == "£28,156 (estimated)"


def test_employer_stated_single_value_has_no_estimated_label():
    result = _format_salary({"salary_min": 30000, "salary_max": 30000, "salary_is_predicted": "0"})
    assert result == "£30,000"


def test_only_one_of_min_or_max_present_still_formats():
    result = _format_salary({"salary_min": 25000, "salary_max": None, "salary_is_predicted": "0"})
    assert result == "£25,000"
