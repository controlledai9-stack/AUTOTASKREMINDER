"""Daily streak tracking.

A "streak" here means consecutive calendar days on which the user's task
completion percentage met or exceeded ``STREAK_COMPLETION_THRESHOLD``
(100% by default, configurable via the ``.env`` file). Each day's final
snapshot is persisted to the ``daily_snapshots`` table so streaks can be
computed cheaply without recalculating historical task states.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from src.config import STREAK_COMPLETION_THRESHOLD
from src.database import get_connection
from src.models import DailySnapshot, ProgressSnapshot
from src.utils import get_logger, today_iso

logger = get_logger(__name__)


def record_snapshot(progress: ProgressSnapshot, date: str | None = None) -> None:
    """Upsert today's (or a given day's) progress snapshot.

    Safe to call multiple times per day (e.g. on every scheduled email) -
    it overwrites the existing row for that date with the latest numbers.

    Args:
        progress: The progress snapshot to persist.
        date: ISO date string to record for. Defaults to today (local tz).
    """
    date = date or today_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_snapshots (date, completed_tasks, total_tasks, completion_pct)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                completed_tasks = excluded.completed_tasks,
                total_tasks = excluded.total_tasks,
                completion_pct = excluded.completion_pct
            """,
            (date, progress.completed_tasks, progress.total_tasks, progress.completed_pct),
        )
        conn.commit()
    logger.info("Recorded snapshot for %s: %.1f%% complete", date, progress.completed_pct)


def get_snapshot_history(limit_days: int = 30) -> List[DailySnapshot]:
    """Return the most recent ``limit_days`` daily snapshots, oldest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM daily_snapshots
            ORDER BY date DESC
            LIMIT ?
            """,
            (limit_days,),
        ).fetchall()
    snapshots = [
        DailySnapshot(
            date=row["date"],
            completed_tasks=row["completed_tasks"],
            total_tasks=row["total_tasks"],
            completion_pct=row["completion_pct"],
        )
        for row in rows
    ]
    return list(reversed(snapshots))  # oldest first, for charting


def compute_current_streak() -> int:
    """Compute the current consecutive-day streak ending today or yesterday.

    A day "counts" toward the streak if its recorded completion percentage
    is >= ``STREAK_COMPLETION_THRESHOLD``. The streak is allowed to include
    today even if today isn't finished yet (it just won't count until the
    threshold is met), and continues backward through yesterday, the day
    before, etc., stopping at the first day that doesn't qualify.

    Returns:
        The number of consecutive qualifying days.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, completion_pct FROM daily_snapshots ORDER BY date DESC"
        ).fetchall()

    if not rows:
        return 0

    snapshots_by_date = {row["date"]: row["completion_pct"] for row in rows}
    streak = 0
    cursor_date = datetime.fromisoformat(today_iso()).date()

    while True:
        date_str = cursor_date.isoformat()
        pct = snapshots_by_date.get(date_str)
        if pct is None:
            # No record for this day - if it's today, just skip (day in
            # progress) and keep checking backward; otherwise the streak
            # ends here.
            if date_str == today_iso():
                cursor_date -= timedelta(days=1)
                continue
            break
        if pct >= STREAK_COMPLETION_THRESHOLD:
            streak += 1
            cursor_date -= timedelta(days=1)
        else:
            break

    return streak


def compute_longest_streak() -> int:
    """Compute the longest historical streak of qualifying days on record."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, completion_pct FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()

    if not rows:
        return 0

    longest = 0
    current = 0
    previous_date = None

    for row in rows:
        this_date = datetime.fromisoformat(row["date"]).date()
        qualifies = row["completion_pct"] >= STREAK_COMPLETION_THRESHOLD

        if previous_date is not None and (this_date - previous_date).days > 1:
            current = 0  # gap in the record breaks the streak

        if qualifies:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

        previous_date = this_date

    return longest
