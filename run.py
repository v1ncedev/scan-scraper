#!/usr/bin/env python3
"""Entrypoint: `python run.py` performs one fetch -> dedup -> notify cycle.

This is what the GitHub Actions workflow calls every 6 hours. All the actual
logic lives in jobalerts/pipeline.py — this file just loads the local .env
file (for running on your own machine) and kicks it off.
"""

from dotenv import load_dotenv

# In GitHub Actions, secrets are already in the environment and there's no
# .env file — load_dotenv() simply does nothing in that case, which is fine.
load_dotenv()

from jobalerts.pipeline import main  # noqa: E402 (import after load_dotenv on purpose)

if __name__ == "__main__":
    main()
