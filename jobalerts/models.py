"""The core data type that flows through the whole pipeline: a single job Posting.

Every source (Adzuna, Greenhouse, ...) converts its own raw JSON into a list of
`Posting` objects, so the rest of the code never has to care where a job came
from. This is the "common shape" that lets us mix sources freely.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class Posting:
    """A normalised job posting.

    We use ``frozen=True`` for two reasons:
      1. It makes the object immutable — once a source has created a Posting,
         nothing downstream can accidentally change it.
      2. Frozen dataclasses are hashable, so Postings can go straight into a
         set/dict if we ever need to (handy for in-memory deduplication).
    """

    # Where the posting came from, e.g. "adzuna" or "greenhouse:monzo".
    # Purely informational — useful in logs and in the notification message.
    source: str

    title: str
    company: str
    location: str
    url: str

    # Some sources give us a date, some don't, so this is optional.
    # (We use typing.Optional rather than the `str | None` shorthand so the code
    # runs on Python 3.9, which Pydantic evaluates at import time.)
    posted_date: Optional[str] = None

    @property
    def _canonical_url(self) -> str:
        """The URL with its query string and fragment stripped.

        Confirmed by testing against the live Adzuna API: its `redirect_url`
        embeds a one-time session token (`?se=...`) that is DIFFERENT on every
        API call, even when it's the exact same job (same underlying job id in
        the URL path). If unique_key hashed the raw URL, the same job would
        look "new" on almost every run and we'd re-notify on it constantly.

        Query strings across job APIs are typically tracking/session noise
        rather than part of a job's real identity, so stripping them before
        hashing is a safe general rule — not an Adzuna-specific special case.
        The original, un-stripped `url` is left untouched for display/linking.
        """
        parsed = urlsplit(self.url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    @property
    def unique_key(self) -> str:
        """A stable fingerprint used to decide whether we've seen this job before.

        We hash the combination of title + company + canonical URL because no
        single field is reliable on its own:
          - The URL's path (job id, board slug) is generally stable, but any
            query string on it can vary between requests for the same job —
            see `_canonical_url` above — so we strip it before hashing.
          - Title + company alone can collide when a company posts the same
            role in multiple locations.
        Combining all three gives a key that is stable across runs but still
        distinguishes genuinely different postings.

        We normalise (strip whitespace + lowercase) first so that trivial
        formatting differences don't make the same job look "new" every run.
        """
        normalised = "|".join(
            part.strip().lower()
            for part in (self.title, self.company, self._canonical_url)
        )
        # SHA-256 is overkill for collision resistance here, but it's in the
        # standard library, deterministic, and gives us a tidy fixed-length key.
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
