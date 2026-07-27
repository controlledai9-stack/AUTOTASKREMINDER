# ✅ AI Daily Progress Tracker

A full-stack Python application for tracking daily tasks, visualizing progress in
real time, and receiving automated email updates - even when your computer is
turned off.

Built with **Streamlit**, **SQLite**, **Gmail SMTP**, and **GitHub Actions**.

---

## Features

- **Task management** - create, edit, delete, categorize, prioritize, and mark
  tasks complete/pending
- **Real-time progress** - live completion %, remaining %, and task counts
- **Dashboard** - metrics, a completion donut chart, and a category breakdown
  chart
- **Analytics tab** - 30-day completion history, priority breakdown, and an
  email send log
- **Filters & search** - by category, priority, status, and free-text search
- **Dark mode toggle**
- **Streak tracking** - current streak and longest streak on record
- **Scheduled email updates** - 9 AM, 12 PM, 3 PM, 6 PM, 9 PM (local time),
  sent via GitHub Actions regardless of whether your machine is on
- **Weekly summary email** - sent every Sunday, with a day-by-day breakdown
- **CSV export** - tasks and full progress history
- **Clean modular architecture** - separate modules for tasks, progress math,
  email, and scheduling, all covered by unit tests

---

## Project Structure

```
ai-daily-progress-tracker/
├── app.py                          # Streamlit UI (entry point)
├── requirements.txt
├── .env.example                    # Copy to .env and fill in credentials
├── data/
│   └── tracker.db                  # SQLite database (see note below)
├── src/
│   ├── config.py                   # Env-based configuration
│   ├── database.py                 # SQLite connection + schema
│   ├── models.py                   # Task / ProgressSnapshot dataclasses
│   ├── task_manager.py             # CRUD operations on tasks
│   ├── progress_calculator.py      # Completion % and breakdown math
│   ├── streak_tracker.py           # Daily snapshot + streak calculations
│   ├── email_service.py            # Email composition + SMTP sending
│   ├── export_service.py           # CSV export helpers
│   └── utils.py                    # Logging + date/time helpers
├── scheduler/
│   └── send_update.py              # CLI script invoked by GitHub Actions
├── .github/workflows/
│   ├── send_progress_email.yml     # 5x/day scheduled progress emails
│   └── send_weekly_summary.yml     # Weekly summary email
├── scripts/
│   └── sync_db.sh                  # Helper: push local task changes to GitHub
├── tests/                          # Pytest unit tests (23 tests)
└── docs/
    └── ARCHITECTURE.md             # Design decisions & data flow
```

---

## Getting Started (Local)

### 1. Clone and install

```bash
git clone <your-fork-url> ai-daily-progress-tracker
cd ai-daily-progress-tracker
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure email credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:

- `EMAIL_ADDRESS` - the Gmail address that will send emails
- `EMAIL_APP_PASSWORD` - a **Gmail App Password** (see below), not your normal
  Gmail password
- `RECIPIENT_EMAIL` - where you want to receive updates (can be the same
  address)

#### Generating a Gmail App Password

1. Enable **2-Step Verification** on the Google account:
   <https://myaccount.google.com/security>
2. Go to <https://myaccount.google.com/apppasswords>
3. Create an app password (choose "Mail" / "Other") and copy the 16-character
   code into `EMAIL_APP_PASSWORD` in your `.env` file.

### 3. Run the app

```bash
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

### 4. Run the tests

```bash
pytest tests/ -v
```

---

## Enabling "Even When My Computer Is Off" Email Delivery

This is the key architectural piece: **GitHub Actions**, not your machine,
sends the scheduled emails. Once configured, emails go out on schedule
whether your laptop is open, closed, or off.

### 1. Push this project to a GitHub repository

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 2. Add your credentials as GitHub Secrets (not `.env`!)

In your GitHub repo: **Settings → Secrets and variables → Actions → New
repository secret**. Add:

| Secret name          | Value                                  |
|-----------------------|-----------------------------------------|
| `EMAIL_ADDRESS`       | Your Gmail address                     |
| `EMAIL_APP_PASSWORD`  | Your 16-character Gmail App Password   |
| `RECIPIENT_EMAIL`     | Where updates should be sent           |

GitHub Secrets are encrypted and never appear in logs - this is the
production-safe equivalent of your local `.env` file. **Never commit your
actual `.env` file.**

### 3. That's it

The two workflows in `.github/workflows/` are already scheduled:

- `send_progress_email.yml` - runs at 9 AM, 12 PM, 3 PM, 6 PM, 9 PM
  **IST (Asia/Kolkata)** by default
- `send_weekly_summary.yml` - runs every Sunday evening

You can also trigger either one manually from the **Actions** tab on GitHub
(via `workflow_dispatch`) to test that email sending works end-to-end.

### Adjusting Schedule Times

GitHub Actions `cron` schedules always run in **UTC**. The shipped workflow
converts 9 AM/12 PM/3 PM/6 PM/9 PM IST (UTC+5:30) to UTC for you. If you live
elsewhere, recompute the five `cron` lines in
`.github/workflows/send_progress_email.yml`:

```
UTC time = Local time - your UTC offset
```

For example, for US Eastern Time (UTC-4 during DST), 9 AM ET = 13:00 UTC, so
the cron line becomes `"0 13 * * *"`. Also update `APP_TIMEZONE` in the
workflow's `env:` block to your IANA timezone name (e.g. `America/New_York`)
so email timestamps display correctly.

---

## ⚠️ Important: How Task Data Reaches GitHub Actions

GitHub Actions runs your workflow in a **fresh, temporary virtual machine**
that only sees whatever is committed to your GitHub repository - it has no
access to your laptop or its files. Since this project uses SQLite (a local
file), that means:

> **The scheduled emails only reflect tasks that have been committed and
> pushed to GitHub.** Adding a task in your local Streamlit app does not, by
> itself, appear in the next scheduled email.

To sync your latest tasks before the next scheduled send, run:

```bash
./scripts/sync_db.sh
```

This commits and pushes `data/tracker.db` to GitHub. Each scheduled workflow
run also commits back its own updates (streak/email-log data) automatically,
so your history stays in sync in both directions.

This is a deliberate, documented trade-off of using SQLite + GitHub Actions
(zero infrastructure cost, no server to maintain) instead of a hosted
database. See `docs/ARCHITECTURE.md` for a discussion of alternatives (e.g.
Turso, Supabase, or a small persistent server) if you want true real-time
sync without a manual push step.

---

## Tech Stack

| Layer            | Choice                          |
|-------------------|----------------------------------|
| UI                | Streamlit                       |
| Charts            | Plotly                          |
| Database          | SQLite (stdlib `sqlite3`)       |
| Email             | `smtplib` + Gmail SMTP          |
| Scheduler         | GitHub Actions (`cron`)          |
| Config            | `python-dotenv`                 |
| Testing           | `pytest`                        |

---

## Code Quality

- **PEP 8** compliant, with docstrings on every public function/class
- **Type hints** throughout `src/`
- **Error handling** - database operations roll back on failure; email
  sending never raises (failures are logged and recorded, so a bad send
  doesn't crash the scheduler)
- **23 unit tests** covering task CRUD, progress math, streak logic, and
  email composition - all isolated from the real database via pytest
  fixtures

Run linting/formatting locally if desired:

```bash
pip install flake8 black
black --check src/ app.py scheduler/
flake8 src/ app.py scheduler/ --max-line-length=100
```

---

## License

This project is provided as a portfolio/reference implementation. Adapt and
reuse freely.
