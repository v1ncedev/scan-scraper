"""Greenhouse careers-board source — our example "direct company scrape".

Many companies use Greenhouse (https://www.greenhouse.io/) as their applicant
tracking system, and Greenhouse exposes a public, unauthenticated JSON API for
each company's job board:

    https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs?content=true

No API key needed — this is genuinely public data, just structured as JSON
rather than an HTML page, which makes it a clean and reliable "scrape".

Unlike Adzuna, this API has no keyword search, so we fetch every open role on
the board and filter client-side by title (and optionally location).

To track another company on Greenhouse, add another entry to the `greenhouse:`
list in config.yaml with that company's board_token — no code change needed.
A different ATS (e.g. Lever) would follow the same pattern: one new module
with a `fetch_<name>(config) -> list[Posting]` function.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from jobalerts.config import GreenhouseSourceConfig
from jobalerts.models import Posting

logger = logging.getLogger(__name__)

_GREENHOUSE_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
_REQUEST_TIMEOUT_SECONDS = 15


def fetch_greenhouse(config: GreenhouseSourceConfig) -> List[Posting]:
    """Fetch and keyword-filter postings from one company's Greenhouse board."""
    if not config.enabled:
        return []

    url = _GREENHOUSE_URL_TEMPLATE.format(board_token=config.board_token)
    # content=true includes the full job description in the response; we don't
    # use it yet, but it's there for anyone extending this to filter on body text.
    response = requests.get(url, params={"content": "true"}, timeout=_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()

    company_name = config.company_name or config.board_token
    keywords_lower = [k.lower() for k in config.keywords]
    where_lower = config.where.lower() if config.where else None

    matched: List[Posting] = []
    for job in data.get("jobs", []):
        title = job.get("title", "").strip()
        title_lower = title.lower()

        # Client-side keyword filter: title must contain at least one keyword.
        if not any(keyword in title_lower for keyword in keywords_lower):
            continue

        location_name = job.get("location", {}).get("name", "Unknown")

        # Optional location filter, e.g. only "London" roles.
        if where_lower and where_lower not in location_name.lower():
            continue

        matched.append(
            Posting(
                source=f"greenhouse:{config.board_token}",
                title=title,
                company=company_name,
                location=location_name,
                url=job.get("absolute_url", ""),
                posted_date=job.get("updated_at"),
            )
        )

    return matched
