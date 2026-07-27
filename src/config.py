"""Centralized application configuration.

All configuration is loaded from environment variables (typically supplied
via a local ``.env`` file for development, or via GitHub Actions "Secrets"
in CI/CD). Nothing in this module should contain hard-coded credentials.

Keeping configuration in a single module means every other module imports
``config`` instead of calling ``os.getenv`` directly, which makes the
required environment variables easy to discover and to validate in one
place (see :func:`validate_email_config`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, List

from dotenv import load_dotenv

# Load variables from a .env file if one is present. In GitHub Actions,
# secrets are injected directly as environment variables and this call is a
# harmless no-op (no .env file exists there).
load_dotenv()

# ---------------------------------------------------------------------------
# Filesystem paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH: Final[Path] = Path(
    os.getenv("DATABASE_PATH", str(DATA_DIR / "tracker.db"))
)

# ---------------------------------------------------------------------------
# Email / SMTP configuration (Gmail SMTP by default)
# ---------------------------------------------------------------------------
SMTP_HOST: Final[str] = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: Final[int] = int(os.getenv("SMTP_PORT", "587"))

EMAIL_ADDRESS: Final[str] = os.getenv("EMAIL_ADDRESS", "")
# This MUST be a Gmail "App Password", not the account's login password.
EMAIL_APP_PASSWORD: Final[str] = os.getenv("EMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL: Final[str] = os.getenv("RECIPIENT_EMAIL", EMAIL_ADDRESS)

# Sender display name used in outgoing emails.
SENDER_NAME: Final[str] = os.getenv("SENDER_NAME", "AI Daily Progress Tracker")

# ---------------------------------------------------------------------------
# Scheduling configuration
# ---------------------------------------------------------------------------
# IANA timezone name used to compute "today" boundaries and to label times
# in emails. Defaults to Asia/Kolkata since the scheduled send times in the
# spec (9 AM, 12 PM, 3 PM, 6 PM, 9 PM) are most naturally read as local time.
TIMEZONE: Final[str] = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

# The nominal local send times. These are informational/display values used
# by the app and docs; the *actual* trigger times are defined by the cron
# expressions in .github/workflows/*.yml (cron always runs in UTC).
SCHEDULED_SEND_TIMES: Final[List[str]] = ["09:00", "12:00", "15:00", "18:00", "21:00"]

# Day of week (Python's date.weekday(): Monday=0) on which the weekly
# summary email is considered "for" - used only for display purposes.
WEEKLY_SUMMARY_WEEKDAY: Final[int] = int(os.getenv("WEEKLY_SUMMARY_WEEKDAY", "6"))  # Sunday

# ---------------------------------------------------------------------------
# Misc application constants
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES: Final[List[str]] = [
    "Work",
    "Personal",
    "Learning",
    "Health",
    "Errands",
    "Other",
]

PRIORITY_LEVELS: Final[List[str]] = ["Low", "Medium", "High"]

# Streak is counted as "kept" for a day if completion percentage is >= this
# threshold. 100 means only a fully-completed day counts.
STREAK_COMPLETION_THRESHOLD: Final[float] = float(
    os.getenv("STREAK_COMPLETION_THRESHOLD", "100")
)


@dataclass(frozen=True)
class EmailConfigStatus:
    """Result of validating the email configuration."""

    is_valid: bool
    missing_fields: List[str] = field(default_factory=list)


def validate_email_config() -> EmailConfigStatus:
    """Check that the required email environment variables are present.

    Returns:
        EmailConfigStatus: ``is_valid`` is False if any required field is
        missing, along with the names of the missing fields so callers can
        surface a helpful error message (in the UI or in CI logs).
    """
    required = {
        "EMAIL_ADDRESS": EMAIL_ADDRESS,
        "EMAIL_APP_PASSWORD": EMAIL_APP_PASSWORD,
        "RECIPIENT_EMAIL": RECIPIENT_EMAIL,
    }
    missing = [name for name, value in required.items() if not value]
    return EmailConfigStatus(is_valid=len(missing) == 0, missing_fields=missing)
