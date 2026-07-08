"""Adzuna API source.

Adzuna aggregates job postings from many boards and exposes a simple REST API.
Docs: https://developer.adzuna.com/docs/search

We make one request per configured keyword (Adzuna's `what` parameter only
accepts a single search phrase) and merge the results into one list.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from jobalerts.config import AdzunaSourceConfig, Settings
from jobalerts.models import Posting

logger = logging.getLogger(__name__)

# Adzuna's search endpoint always uses page 1 here — we only want the newest
# handful of results per keyword, not exhaustive pagination.
_ADZUNA_URL_TEMPLATE = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# Keep the tool responsive even if Adzuna is slow or unreachable — this is what
# lets safe_fetch() move on and log a failure instead of hanging the whole run.
_REQUEST_TIMEOUT_SECONDS = 15


def fetch_adzuna(config: AdzunaSourceConfig, country: str, settings: Settings) -> List[Posting]:
    """Fetch postings from Adzuna for every keyword in ``config.keywords``.

    Returns an empty list immediately if the source is disabled in config.
    """
    if not config.enabled:
        return []

    all_postings: List[Posting] = []
    url = _ADZUNA_URL_TEMPLATE.format(country=country)

    for keyword in config.keywords:
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": keyword,
            "results_per_page": config.results_per_page,
            "max_days_old": config.max_days_old,
            "content-type": "application/json",
        }
        # Only send `where` when a specific place is configured. Sending an
        # unset/country-level value here isn't just redundant — passing e.g.
        # "United Kingdom" causes Adzuna to silently return zero results, since
        # it can't resolve a country name as a place within the already-scoped
        # country. Omitting the param entirely gives a nationwide search.
        if config.where:
            params["where"] = config.where
        # Adzuna only accepts the category param when it's set to a real slug;
        # omit it entirely rather than sending category=None.
        if config.category:
            params["category"] = config.category

        response = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        # Raises requests.HTTPError on a 4xx/5xx response (e.g. bad app_id/app_key,
        # or Adzuna being down). safe_fetch() in the caller catches this so one
        # bad keyword/request doesn't take down the whole source.
        response.raise_for_status()
        data = response.json()

        for result in data.get("results", []):
            all_postings.append(
                Posting(
                    source="adzuna",
                    title=result.get("title", "").strip(),
                    company=result.get("company", {}).get("display_name", "Unknown"),
                    location=result.get("location", {}).get("display_name", "Unknown"),
                    url=result.get("redirect_url", ""),
                    posted_date=result.get("created"),
                )
            )

    return all_postings
