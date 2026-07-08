"""Telegram notifications for newly-found postings.

We batch every new posting from a single run into as few messages as
possible, rather than sending one Telegram message per job — nobody wants
fifteen separate pings because fifteen graduate roles appeared at once.

Telegram caps a single message at 4096 characters, so if a big batch of new
postings would produce a longer message than that, we split it into multiple
chunks (each chunk is still a whole number of postings — we never cut a job's
entry in half).
"""

from __future__ import annotations

import logging
from typing import List

import requests

from jobalerts.config import Settings
from jobalerts.models import Posting

logger = logging.getLogger(__name__)

_TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 15

# Telegram's hard limit on a single message's text. We leave a small margin
# below the true 4096 limit for safety.
_MAX_MESSAGE_LENGTH = 4000


def _format_posting(posting: Posting) -> str:
    """Render one posting as an HTML snippet for a Telegram message.

    Telegram's HTML mode supports a small set of tags (b, i, a, ...); we only
    need bold and a link, so we avoid pulling in a templating library for it.
    """
    # Not every source has salary data (Greenhouse's public API has no
    # structured salary field), so this line is only included when present.
    salary_line = f"💰 {posting.salary}\n" if posting.salary else ""
    return (
        f"<b>{posting.title}</b> — {posting.company}\n"
        f"📍 {posting.location}\n"
        f"{salary_line}"
        f'🔗 <a href="{posting.url}">View posting</a>'
    )


def _build_messages(postings: List[Posting]) -> List[str]:
    """Group formatted postings into as few messages as possible, respecting
    Telegram's length limit.

    Each returned string is a complete, ready-to-send message body.
    """
    header = f"🎯 {len(postings)} new job posting(s) found:\n\n"
    entry_separator = "\n\n"

    messages: List[str] = []
    current_chunks: List[str] = []
    current_length = len(header)

    for posting in postings:
        entry = _format_posting(posting)
        added_length = len(entry) + len(entry_separator)

        if current_chunks and current_length + added_length > _MAX_MESSAGE_LENGTH:
            # This posting would overflow the current message — start a new one.
            messages.append(header + entry_separator.join(current_chunks))
            current_chunks = []
            current_length = len(header)

        current_chunks.append(entry)
        current_length += added_length

    if current_chunks:
        messages.append(header + entry_separator.join(current_chunks))

    return messages


def send_telegram(settings: Settings, postings: List[Posting]) -> bool:
    """Send all new postings to Telegram, batched into as few messages as possible.

    Returns True only if every message sent successfully. The pipeline uses
    this to decide whether it's safe to mark these postings as "seen" — if
    Telegram is down, we'd rather retry the notification next run than lose
    the alert silently.
    """
    if not postings:
        return True  # nothing to send is trivially a success

    url = _TELEGRAM_API_TEMPLATE.format(token=settings.telegram_bot_token)
    messages = _build_messages(postings)

    for message in messages:
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except Exception:
            logger.exception("Failed to send Telegram notification")
            return False

    logger.info(
        "Sent %d new posting(s) to Telegram in %d message(s)",
        len(postings),
        len(messages),
    )
    return True
