"""jobalerts — a small, config-driven job-alert automation tool.

The package is organised as a one-way pipeline, one module per responsibility:

    sources/  -> fetch postings from Adzuna and company career boards
    database  -> remember which postings we have already seen (deduplication)
    notifier  -> send new postings to Telegram
    pipeline  -> wire the above together in the right order

See README.md for the full architecture overview.
"""

__version__ = "0.1.0"
