"""Unit tests for src.streak_tracker."""

from __future__ import annotations

from datetime import date, timedelta

from src import streak_tracker
from src.database import get_connection
from src.models import ProgressSnapshot


def _snapshot(completed: int, total: int) -> ProgressSnapshot:
    pct = round((completed / total) * 100, 1) if total else 0.0
    return ProgressSnapshot(
        total_tasks=total,
        completed_tasks=completed,
        pending_tasks=total - completed,
        completed_pct=pct,
        remaining_pct=round(100 - pct, 1),
        by_category={},
        by_priority={},
    )


def _insert_snapshot_for_date(iso_date: str, completed: int, total: int) -> None:
    pct = round((completed / total) * 100, 1) if total else 0.0
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_snapshots (date, completed_tasks, total_tasks, completion_pct)
            VALUES (?, ?, ?, ?)
            """,
            (iso_date, completed, total, pct),
        )
        conn.commit()


def test_record_snapshot_upserts_for_same_date():
    streak_tracker.record_snapshot(_snapshot(1, 4), date="2026-07-24")
    streak_tracker.record_snapshot(_snapshot(4, 4), date="2026-07-24")

    history = streak_tracker.get_snapshot_history(limit_days=5)
    assert len(history) == 1
    assert history[0].completion_pct == 100.0


def test_current_streak_counts_consecutive_full_days():
    today = date.today()
    for i in range(3):
        d = (today - timedelta(days=i)).isoformat()
        _insert_snapshot_for_date(d, completed=5, total=5)

    assert streak_tracker.compute_current_streak() == 3


def test_current_streak_stops_at_incomplete_day():
    today = date.today()
    _insert_snapshot_for_date(today.isoformat(), completed=5, total=5)
    _insert_snapshot_for_date((today - timedelta(days=1)).isoformat(), completed=2, total=5)
    _insert_snapshot_for_date((today - timedelta(days=2)).isoformat(), completed=5, total=5)

    # Streak should stop after today because yesterday didn't qualify.
    assert streak_tracker.compute_current_streak() == 1


def test_longest_streak_finds_historical_max():
    base = date(2026, 7, 1)
    # 3-day streak, gap, then 5-day streak
    for i in range(3):
        _insert_snapshot_for_date((base + timedelta(days=i)).isoformat(), 5, 5)
    _insert_snapshot_for_date((base + timedelta(days=3)).isoformat(), 1, 5)  # breaks streak
    for i in range(4, 9):
        _insert_snapshot_for_date((base + timedelta(days=i)).isoformat(), 5, 5)

    assert streak_tracker.compute_longest_streak() == 5


def test_longest_streak_with_no_data_is_zero():
    assert streak_tracker.compute_longest_streak() == 0
