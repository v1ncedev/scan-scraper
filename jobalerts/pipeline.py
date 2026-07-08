"""Orchestrates one full run of the job-alert tool.

This module wires together every other piece in the order described in the
README's architecture diagram:

    fetch  ->  dedup  ->  (silent seed | notify)  ->  mark as seen

Kept deliberately thin and readable — if you want to understand what happens
during a scheduled run, this file is the place to start.
"""

from __future__ import annotations

import logging

from jobalerts.config import Settings, load_config
from jobalerts.database import filter_new, init_db, is_first_run, mark_seen
from jobalerts.notifier import send_telegram
from jobalerts.sources import fetch_all_postings

logger = logging.getLogger(__name__)

_DB_PATH = "data/seen_jobs.db"
_CONFIG_PATH = "config.yaml"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings()  # secrets from environment / .env
    config = load_config(_CONFIG_PATH)  # search parameters from config.yaml

    conn = init_db(_DB_PATH)
    first_run = is_first_run(conn)  # must check BEFORE we insert anything below

    all_postings = fetch_all_postings(config, settings)
    new_postings = filter_new(conn, all_postings)

    logger.info(
        "Fetched %d posting(s) total, %d are new",
        len(all_postings),
        len(new_postings),
    )

    if first_run:
        # Don't alert on a database's worth of jobs that already existed
        # before we started watching — just record them as the baseline.
        mark_seen(conn, new_postings)
        logger.info(
            "First run detected: seeded %d posting(s) silently, no notification sent",
            len(new_postings),
        )
    elif new_postings:
        sent_ok = send_telegram(settings, new_postings)
        if sent_ok:
            # Only mark postings as seen once we know Telegram actually
            # accepted the message. If Telegram is down, we deliberately
            # leave them unmarked so the NEXT run notices them as "new"
            # again and retries the alert, rather than losing them silently.
            mark_seen(conn, new_postings)
            logger.info("Notified Telegram and marked %d posting(s) as seen", len(new_postings))
        else:
            logger.error(
                "Telegram notification failed; leaving %d posting(s) unmarked for retry next run",
                len(new_postings),
            )
    else:
        logger.info("No new postings this run")

    conn.close()


if __name__ == "__main__":
    main()
