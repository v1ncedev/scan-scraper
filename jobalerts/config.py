"""Configuration handling, split into two clearly separate concerns:

  1. Non-secret settings (what to search for) live in ``config.yaml`` and are
     described by the Pydantic models below. Pydantic validates the file at load
     time, so a typo like ``keyword:`` instead of ``keywords:`` fails loudly with
     a helpful message instead of causing a confusing crash later.

  2. Secrets (API keys, tokens) never go in the YAML file. They come from
     environment variables (a local ``.env`` file in development, GitHub Actions
     Secrets in CI) and are described by the ``Settings`` class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Non-secret config models (loaded from config.yaml)
# ---------------------------------------------------------------------------


class AdzunaSourceConfig(BaseModel):
    """Search parameters for the Adzuna API source."""

    # Whether to query this source at all. Lets you switch a source off from
    # the config file without deleting its settings.
    enabled: bool = True

    # The search terms. We run one API request per keyword and merge the
    # results, so ["graduate", "data analyst"] searches for both.
    keywords: list[str] = Field(min_length=1)

    # Adzuna's location filter, e.g. "London" or "Manchester".
    #
    # Country-level scoping already comes from the top-level `country` field
    # (used in the API URL path, e.g. .../jobs/gb/search/1), so `where` should
    # only ever hold a place *within* that country. Passing a country name
    # here (e.g. "United Kingdom") is redundant and — confirmed by testing
    # against the live API — silently returns zero results instead of an
    # error, because Adzuna can't match it as a UK place name. Leave this
    # unset (None) for a nationwide search, or set a specific city/region to
    # narrow it down.
    where: Optional[str] = None

    # Optional Adzuna category slug (e.g. "it-jobs", "graduate-jobs").
    # See https://developer.adzuna.com/docs/categories for the full list.
    # None means "don't filter by category".
    category: Optional[str] = None

    # How many results to ask for per keyword (Adzuna free tier allows up to 50).
    results_per_page: int = Field(default=20, ge=1, le=50)

    # Only consider postings created within this many days. Keeps the alerts
    # focused on fresh jobs and reduces noise on the first run.
    max_days_old: int = Field(default=7, ge=1)


class GreenhouseSourceConfig(BaseModel):
    """Settings for scraping one company's Greenhouse job board.

    Greenhouse exposes a public JSON API per company at
    ``boards-api.greenhouse.io/v1/boards/<board_token>/jobs``. The board token
    is the company's identifier in that URL (e.g. "monzo").
    """

    enabled: bool = True

    # The company's Greenhouse board token (the slug in the API URL).
    board_token: str

    # A friendly company name to show in notifications. If omitted we fall back
    # to the board token.
    company_name: Optional[str] = None

    # Only keep postings whose title contains one of these keywords
    # (case-insensitive). Greenhouse has no server-side keyword filter, so we
    # filter client-side after fetching the full board.
    keywords: list[str] = Field(min_length=1)

    # Optional case-insensitive substring filter on the job's location, e.g.
    # "London". None means "any location".
    where: Optional[str] = None


class AppConfig(BaseModel):
    """The top-level shape of config.yaml."""

    # Adzuna country code used in the API path, e.g. "gb" for the UK.
    country: str = "gb"

    adzuna: AdzunaSourceConfig

    # A list so you can track as many companies as you like — adding one is
    # just another entry here, no code change required.
    greenhouse: list[GreenhouseSourceConfig] = Field(default_factory=list)


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Read and validate the YAML config file into an :class:`AppConfig`.

    Raises:
        FileNotFoundError: if the config file doesn't exist.
        pydantic.ValidationError: if the file is missing required fields or has
            the wrong types — the message points at the exact problem field.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    # ``**raw`` hands the parsed YAML dict to Pydantic, which validates it and
    # constructs the nested config objects for us.
    return AppConfig(**raw)


# ---------------------------------------------------------------------------
# Secret settings (loaded from environment variables / .env)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Secrets read from the environment.

    ``pydantic-settings`` matches each field to an environment variable of the
    same name, case-insensitively — so ``adzuna_app_id`` is populated from the
    ``ADZUNA_APP_ID`` environment variable. Locally we also load a ``.env`` file
    (see ``model_config``); in GitHub Actions the variables come from Secrets.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore any unrelated variables that happen to be in the environment.
        extra="ignore",
    )

    adzuna_app_id: str
    adzuna_app_key: str
    telegram_bot_token: str
    telegram_chat_id: str
