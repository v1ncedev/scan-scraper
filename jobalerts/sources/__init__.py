"""Source registry — the single place that knows which sources exist.

``fetch_all_postings`` is the one function the rest of the app calls. It loops
over every configured source, fetches each one through ``safe_fetch`` (so a
single failure never aborts the run), and returns the combined list.

To add a brand-new *kind* of source (not just another Greenhouse company, but
e.g. a Lever board or a different API): write a `fetch_<name>` function in a
new module here, then add one more block to the loop below that calls it
through `safe_fetch`. Adding another *company* on an existing source (e.g.
another Greenhouse board) needs no code change at all — just another entry
in config.yaml's `greenhouse:` list.
"""

from __future__ import annotations

import logging
from typing import List

from jobalerts.config import AppConfig, Settings
from jobalerts.models import Posting
from jobalerts.sources.adzuna import fetch_adzuna
from jobalerts.sources.base import safe_fetch
from jobalerts.sources.greenhouse import fetch_greenhouse

logger = logging.getLogger(__name__)


def fetch_all_postings(config: AppConfig, settings: Settings) -> List[Posting]:
    """Fetch postings from every enabled source and merge them into one list."""
    postings: List[Posting] = []

    # --- Adzuna: one source, config-driven keyword list ---
    postings.extend(
        safe_fetch("adzuna", lambda: fetch_adzuna(config.adzuna, config.country, settings))
    )

    # --- Greenhouse: potentially many companies, each fetched independently ---
    # A late-binding closure bug lurks here if we're not careful: capturing
    # `gh_config` by reference in a loop-defined lambda would make every
    # lambda see the *last* company's config. Binding it as a default
    # argument (`gh=gh_config`) captures the value at definition time instead.
    for gh_config in config.greenhouse:
        source_label = f"greenhouse:{gh_config.board_token}"
        postings.extend(
            safe_fetch(source_label, lambda gh=gh_config: fetch_greenhouse(gh))
        )

    return postings
