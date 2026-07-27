# Architecture

## Overview

AI Daily Progress Tracker is split into three independent layers that only
communicate through the `src/` package's public functions:

```
┌─────────────────┐      ┌──────────────────────┐      ┌───────────────────┐
│   app.py         │      │  scheduler/          │      │   src/            │
│   (Streamlit UI) │─────▶│  send_update.py      │─────▶│   (business logic)│
│                  │      │  (CLI, run by CI)    │      │                   │
└─────────────────┘      └──────────────────────┘      └───────────────────┘
                                                                  │
                                                                  ▼
                                                         ┌───────────────────┐
                                                         │  data/tracker.db  │
                                                         │  (SQLite)         │
                                                         └───────────────────┘
```

Neither `app.py` nor `scheduler/send_update.py` contains any business logic
itself - both are thin entry points that call into `src/`. This means:

- The Streamlit app and the GitHub Actions scheduler always compute progress
  identically (same functions, same rules) - there's no risk of the UI and
  the emails disagreeing about "75% complete."
- Every piece of logic in `src/` is unit-testable without spinning up
  Streamlit or sending real emails (see `tests/`).

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Single source of truth for environment-derived settings |
| `database.py` | Connection lifecycle + schema (`tasks`, `daily_snapshots`, `email_log`) |
| `models.py` | Dataclasses: `Task`, `ProgressSnapshot`, `DailySnapshot` |
| `task_manager.py` | All SQL touching the `tasks` table (CRUD + filtering) |
| `progress_calculator.py` | Pure functions: given tasks, compute percentages/breakdowns |
| `streak_tracker.py` | Persists daily snapshots; computes current/longest streak |
| `email_service.py` | Builds HTML emails; sends via SMTP; logs attempts |
| `export_service.py` | CSV serialization for tasks and history |
| `utils.py` | Logging setup, timezone-aware date helpers |

## Why SQLite + GitHub Actions (and its trade-off)

The brief calls for zero-infrastructure, "keeps working when your computer is
off" email delivery, using SQLite for storage. GitHub Actions is a free,
serverless cron runner that satisfies the "always on" requirement without
renting a server - but each workflow run starts from a **fresh checkout of
the git repository**, with no access to your local filesystem.

This has one direct consequence, called out prominently in the README:

> The GitHub Actions job can only see task data that has been **committed to
> the repository**. It cannot reach into your laptop's local
> `data/tracker.db`.

The project resolves this by:

1. Tracking `data/tracker.db` in git (deliberately **not** gitignored).
2. Providing `scripts/sync_db.sh` so you can push local task changes with one
   command before the next scheduled send.
3. Having each GitHub Actions run commit its own writes (new snapshot rows,
   email log entries) back to the repo, so history persists across runs
   without you having to do anything.

### Alternatives, if you want true real-time sync

If committing task data to git isn't a good fit for your workflow, the
`task_manager.py` / `database.py` boundary is intentionally the only place
that knows about SQLite. Swapping storage backends means changing those two
files only - `app.py`, `scheduler/send_update.py`, and everything else in
`src/` are unaffected. Reasonable upgrades:

- **Turso / libSQL** - SQLite-compatible, hosted, has a Python client;
  minimal code changes since the SQL stays the same.
- **Supabase / a managed Postgres** - more setup, but gives you a real
  always-on database both the Streamlit app and GitHub Actions can hit
  directly over the network, with no git-sync step at all.
- **A small persistent server** (e.g. a Fly.io/Render free-tier instance
  running the Streamlit app itself) - then GitHub Actions can just call an
  API endpoint instead of needing the database file at all.

## Data Flow: A Scheduled Email

1. GitHub Actions cron trigger fires (e.g. 09:00 IST → `30 3 * * *` UTC).
2. The workflow checks out the repo (`data/tracker.db` included), installs
   dependencies, and runs `python scheduler/send_update.py --type progress`.
3. `send_update.py` calls `task_manager.get_all_tasks()`, then
   `progress_calculator.compute_progress()`, then
   `streak_tracker.record_snapshot()` + `compute_current_streak()`.
4. `email_service.build_progress_email_html()` renders the HTML email
   (motivational message + progress bar + task lists + streak).
5. `email_service.send_email()` logs into Gmail SMTP with the credentials
   from GitHub Secrets and sends the message; the attempt (success/failure)
   is written to the `email_log` table.
6. The workflow commits and pushes the updated `data/tracker.db` back to the
   repository so the new snapshot/log rows aren't lost.

## Testing Strategy

Tests in `tests/` use an `autouse` pytest fixture (`conftest.py`) that points
`src.database.DATABASE_PATH` at a temporary file for the duration of each
test, so:

- Tests never touch your real `data/tracker.db`.
- Tests can run in any order and don't leak state into each other.
- `email_service` tests never make real network calls - they test HTML
  composition and the "missing configuration" guard clause, not SMTP itself.
