"""Shared building blocks for job sources.

Every source module (adzuna.py, greenhouse.py, ...) exposes one function that
takes some config and returns a ``list[Posting]``. This file defines:

  - ``JobSource``: a typing.Protocol describing that shape, so we get type
    checking without forcing every source into a rigid class hierarchy.
  - ``safe_fetch``: a wrapper that calls a source and guarantees it can never
    crash the whole pipeline. This is where the "log and skip" requirement
    lives — one dead source (bad API key, site down, unexpected JSON) just
    logs an error and contributes zero postings, instead of stopping every
    other source from running too.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Protocol

from jobalerts.models import Posting

logger = logging.getLogger(__name__)


class JobSource(Protocol):
    """Anything callable with no arguments that returns a list of Postings.

    We don't actually need to reference this type anywhere at runtime — it's
    documentation-as-code for what a "fetch function" looks like, and lets
    editors/type-checkers flag a source that doesn't match the shape.
    """

    def __call__(self) -> List[Posting]:
        ...


def safe_fetch(source_name: str, fetch_fn: Callable[[], List[Posting]]) -> List[Posting]:
    """Run ``fetch_fn`` and never let it raise.

    Args:
        source_name: A short label used in log messages, e.g. "adzuna" or
            "greenhouse:monzo".
        fetch_fn: A zero-argument callable that fetches and returns postings.

    Returns:
        Whatever ``fetch_fn`` returned, or an empty list if it raised any
        exception. The exception (with traceback) is logged so the failure is
        still visible in the GitHub Actions run history.
    """
    try:
        postings = fetch_fn()
        logger.info("%s: fetched %d posting(s)", source_name, len(postings))
        return postings
    except Exception:
        # A bare `except Exception` is normally too broad, but here it's the
        # point: any single source failing (network error, bad credentials,
        # a site changing its response shape) must not take down the other
        # sources or the whole scheduled run.
        logger.exception("%s: fetch failed, skipping this source", source_name)
        return []
