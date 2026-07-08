# Job Alerts

A small, config-driven automation tool that watches for new graduate and
entry-level job postings and sends me a Telegram notification when one
appears — no dashboards to check, no manually re-running searches.

It runs on a schedule via GitHub Actions, needs no server of my own, and
costs nothing to operate (free-tier API, free-tier bot, free-tier CI
minutes).

## Why I built this

I wanted a small, complete, real-world project to sharpen practical Python:
working with external HTTP APIs, structuring code as a pipeline rather than
one big script, using a database for state instead of stuffing everything
into memory, and shipping something that actually runs unattended in
production (GitHub Actions) rather than just on my own laptop. Every module
below is something I can walk through and explain line by line.

## What it does

Every 6 hours, the tool:

1. **Fetches** postings from every enabled source in [`config.yaml`](config.yaml):
   - [Adzuna](https://developer.adzuna.com/) — a UK job aggregator API,
     searched with a configurable list of keywords (e.g. "graduate", "data
     analyst").
   - Any company's [Greenhouse](https://www.greenhouse.io/) careers board —
     Greenhouse exposes a public JSON API per company, so this is a genuine
     "scrape a company's careers page" source, just via clean JSON instead of
     parsing HTML. Ships with Monzo configured as a working example.
2. **Deduplicates** the results against a SQLite database of postings it's
   already seen (by a hash of title + company + a canonicalised URL — see
   [Design notes](#design-notes-worth-knowing) for why "canonicalised"
   matters).
3. **Notifies** me on Telegram — all new postings from one run are batched
   into as few messages as possible, rather than one ping per job.
4. **Commits** its updated database back to the repo, so the next scheduled
   run (on a brand-new, empty GitHub Actions runner) remembers what it's
   already alerted on.

### Example notification

> 🎯 3 new job posting(s) found:
>
> **Graduate Data Analyst** — Monzo
> 📍 Cardiff, London or Remote (UK)
> 🔗 [View posting](#)
>
> **Junior Software Engineer** — Wise
> 📍 London
> 🔗 [View posting](#)
>
> **Data Analyst Graduate Scheme** — NHS Digital
> 📍 Leeds
> 🔗 [View posting](#)

*(Add a real screenshot here once you've received your first live alert —
`docs/example-notification.png` and reference it with
`![Example notification](docs/example-notification.png)`.)*

## Architecture

One-way pipeline, one module per responsibility:

```
config.yaml + environment secrets
        │
        ▼
┌───────────────┐
│   sources/    │  Adzuna API + Greenhouse JSON → list[Posting]
│ (fetch, each  │  Each source is fetched through safe_fetch(), which logs
│  isolated)    │  and skips a failing source instead of crashing the run.
└───────┬───────┘
        ▼
┌───────────────┐
│   database    │  filter_new(): keep only postings not already in SQLite
└───────┬───────┘
        │
        ├─ first run ever? → mark_seen(), send NOTHING (silent seed)
        │
        ▼
┌───────────────┐
│   notifier    │  batch every new posting into as few Telegram messages
│               │  as possible (Telegram's 4096-char limit is respected)
└───────┬───────┘
        ▼
   mark_seen() — but ONLY if the Telegram send succeeded, so a Telegram
   outage doesn't silently lose an alert; it just retries next run
        │
        ▼
GitHub Actions commits data/seen_jobs.db back to the repo
```

### Project layout

```
jobalerts/
├── models.py          # Posting — the one data shape every source produces
├── config.py          # Pydantic-validated config.yaml + secrets (Settings)
├── database.py        # SQLite dedup store: init / is_first_run / filter_new / mark_seen
├── notifier.py         # Telegram sendMessage, with batching + length-limit chunking
├── pipeline.py         # Orchestrates fetch → dedup → notify → mark, in that order
└── sources/
    ├── base.py         # safe_fetch() — the one place "log and skip" is enforced
    ├── adzuna.py        # Adzuna API fetcher
    └── greenhouse.py    # Greenhouse board fetcher (pluggable — see below)
tests/                  # pytest unit tests for models, config, and database
run.py                  # Entrypoint: loads .env locally, then calls pipeline.main()
config.yaml             # Editable search terms — the only file most changes need
.github/workflows/      # The 6-hourly scheduled GitHub Actions workflow
```

### Adding another source

- **Another company on an existing source** (e.g. another Greenhouse board):
  add one more entry to the `greenhouse:` list in `config.yaml`. No code
  change.
- **A different kind of source entirely** (e.g. a Lever board): add a new
  `fetch_<name>(config) -> list[Posting]` function in `jobalerts/sources/`,
  following the same shape as `fetch_greenhouse`, then call it through
  `safe_fetch` in `jobalerts/sources/__init__.py`.

## Setup

### 1. Clone and install dependencies

```bash
git clone <this-repo-url>
cd scan-scraper
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get Adzuna API credentials (free)

1. Register at [developer.adzuna.com](https://developer.adzuna.com/) —
   just an email address, no card required.
2. Your dashboard shows a default app with an **Application ID** and
   **Application Key**. Copy both.

### 3. Create a Telegram bot and find your chat ID

1. In Telegram, message **[@BotFather](https://t.me/BotFather)** and send
   `/newbot`. Give it a display name and a username ending in `bot`.
2. BotFather replies with a **bot token** — copy it.
3. Open a chat with your new bot and send it any message (e.g. `/start`) —
   Telegram requires this before a bot can message you.
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
   and find `"chat":{"id": ...}` in the response — that number is your
   **chat ID**.

### 4. Configure secrets locally

```bash
cp .env.example .env
```

Edit `.env` and fill in the four values from steps 2–3. This file is
git-ignored — it's for local testing only and is never committed.

### 5. Edit your search terms

Open [`config.yaml`](config.yaml) (or copy from
[`config.example.yaml`](config.example.yaml)) and adjust `keywords`,
`where`, `category`, and the `greenhouse:` company list to whatever you
want to track. No code changes needed for this.

### 6. Test locally

```bash
python run.py
```

**Expect the first run to seed silently** — it records every posting it
finds as "already seen" but sends **no** Telegram notification, so you
aren't blasted with every job that already existed before you started
watching. From the second run onward, only genuinely new postings trigger
an alert. Run `python run.py` again to confirm you see `0 are new` in the
log output (or check `pytest` — see below).

### 7. Run the test suite

```bash
pytest
```

### 8. Configure GitHub Actions secrets

Push this repo to GitHub, then go to
**Settings → Secrets and variables → Actions → New repository secret** and
add each of these (same names as in `.env`):

| Secret name | Value |
|---|---|
| `ADZUNA_APP_ID` | your Adzuna application ID |
| `ADZUNA_APP_KEY` | your Adzuna application key |
| `TELEGRAM_BOT_TOKEN` | your Telegram bot token |
| `TELEGRAM_CHAT_ID` | your Telegram chat ID |

### 9. Enable the scheduled workflow

The workflow at
[`.github/workflows/job-alerts.yml`](.github/workflows/job-alerts.yml) runs
automatically every 6 hours (`cron: '0 */6 * * *'`) once the repo is on
GitHub with Actions enabled. You can also trigger it manually any time from
the **Actions** tab via **Run workflow** (`workflow_dispatch`) — useful for
testing without waiting for the next scheduled slot.

## Design notes worth knowing

A few decisions here aren't obvious from the code alone, and came out of
testing against the real APIs rather than being planned upfront:

- **Why the dedup key strips the URL's query string.** While testing the
  pipeline end-to-end, a second run in a row reported dozens of postings as
  "new" that had already been seen seconds earlier. The cause: Adzuna's
  `redirect_url` embeds a one-time session token (`?se=...`) that's
  **different on every API call**, even for the exact same job (confirmed by
  fetching the same search twice and comparing — same stable job ID in the
  URL path, different query string each time). `Posting.unique_key` now
  hashes a canonicalised URL (path only, no query string) instead of the raw
  URL — see `jobalerts/models.py`. The original URL, tracking parameters and
  all, is left untouched for the actual notification link.
- **Why the DB is committed back to the repo rather than cached.** GitHub
  Actions runners are thrown away after every run, so the SQLite file has to
  be persisted somewhere external. `actions/cache` and workflow artifacts
  were both considered, but caches can be silently evicted (7 days of
  inactivity) and artifacts expire — either would quietly reset the dedup
  state without any obvious warning. Committing the file is the simplest
  option that's guaranteed durable; the tradeoff is bot-authored commits in
  the repo's history and a binary file living in git. The commit message
  includes `[skip ci]` so it doesn't trigger another workflow run.
  - This is also why `data/seen_jobs.db` is **not** in `.gitignore` — that's
    deliberate, not an oversight.
- **Why `where: United Kingdom` doesn't work as an Adzuna filter.** The
  Adzuna API's country is already set via the URL path (e.g.
  `.../jobs/gb/search/1`), so its `where` parameter expects a place *within*
  that country (e.g. "London"), not the country name again. Passing a
  country name there doesn't error — it silently returns zero results. The
  default config leaves `where` unset for a nationwide search.
- **Why a Telegram send failure doesn't mark postings as seen.** If
  Telegram is briefly unreachable, we'd rather the same postings show up
  as "new" again next run (and get retried) than have them marked seen
  and effectively lost. `mark_seen()` is only called after
  `send_telegram()` returns `True`.
- **Why every source is wrapped in `safe_fetch()`.** One source being down
  (bad credentials, a company taking their careers page offline, a JSON
  shape changing) should never stop every *other* source from running. Any
  exception during a fetch is logged with a full traceback and treated as
  "this source found zero jobs this run" rather than crashing the whole
  scheduled job.

## Requirements / dependencies

See [`requirements.txt`](requirements.txt). Runtime: `requests`, `PyYAML`,
`pydantic`, `pydantic-settings`, `python-dotenv`. Dev-only: `pytest`.
