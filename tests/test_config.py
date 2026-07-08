"""Tests for jobalerts.config — the Pydantic-validated config.yaml loader.

The key behaviour worth testing here is that a mistake in config.yaml (a typo,
a missing required field, wrong type) fails loudly and specifically, rather
than causing a confusing crash somewhere deep in a source module.
"""

import pytest
from pydantic import ValidationError

from jobalerts.config import AppConfig, GreenhouseSourceConfig


def test_valid_minimal_config_parses():
    config = AppConfig(
        country="gb",
        adzuna={"keywords": ["graduate"]},
    )
    assert config.country == "gb"
    assert config.adzuna.keywords == ["graduate"]
    # Defaults should kick in for everything we didn't specify.
    assert config.adzuna.where is None
    assert config.adzuna.results_per_page == 20
    assert config.greenhouse == []


def test_missing_required_keywords_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(country="gb", adzuna={})  # keywords is required, min_length=1

    # The error should point specifically at the missing field, not just say
    # "something went wrong" — this is the whole point of using Pydantic here.
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("adzuna", "keywords") for err in errors)


def test_empty_keywords_list_is_rejected():
    with pytest.raises(ValidationError):
        AppConfig(country="gb", adzuna={"keywords": []})


def test_results_per_page_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        AppConfig(country="gb", adzuna={"keywords": ["graduate"], "results_per_page": 100})


def test_greenhouse_entries_default_company_name_is_optional():
    gh = GreenhouseSourceConfig(board_token="monzo", keywords=["graduate"])
    assert gh.company_name is None
    assert gh.enabled is True
    assert gh.where is None
