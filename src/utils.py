"""Small shared utility helpers used across the codebase."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import TIMEZONE


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured with a consistent format.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance. Repeated calls with
        the same name reuse the same underlying logger (standard library
        behavior), so handlers are only attached once.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def now_local() -> datetime:
    """Current datetime in the application's configured timezone."""
    return datetime.now(ZoneInfo(TIMEZONE))


def today_iso() -> str:
    """Today's date as an ISO string (``YYYY-MM-DD``) in the local timezone."""
    return now_local().date().isoformat()


def format_timestamp_for_display(iso_timestamp: str) -> str:
    """Format an ISO timestamp string into a friendly display string.

    Falls back to returning the original string unchanged if it can't be
    parsed, so this is always safe to call on user-facing data.
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %d, %Y %I:%M %p")
    except (ValueError, TypeError):
        return iso_timestamp
