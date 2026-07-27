"""Unit tests for src.progress_calculator (pure functions, no database)."""

from __future__ import annotations

from src.models import Task
from src.progress_calculator import (
    compute_progress,
    get_completed_task_titles,
    get_pending_task_titles,
)


def _make_task(title: str, completed: bool, category: str = "Work", priority: str = "Medium") -> Task:
    return Task(
        id=None,
        title=title,
        category=category,
        priority=priority,
        status="completed" if completed else "pending",
        completed_at="2026-07-24T10:00:00" if completed else None,
    )


def test_compute_progress_with_empty_list():
    snapshot = compute_progress([])
    assert snapshot.total_tasks == 0
    assert snapshot.completed_pct == 0.0
    assert snapshot.remaining_pct == 0.0


def test_compute_progress_percentages():
    tasks = [
        _make_task("A", completed=True),
        _make_task("B", completed=True),
        _make_task("C", completed=False),
        _make_task("D", completed=False),
    ]
    snapshot = compute_progress(tasks)
    assert snapshot.total_tasks == 4
    assert snapshot.completed_tasks == 2
    assert snapshot.pending_tasks == 2
    assert snapshot.completed_pct == 50.0
    assert snapshot.remaining_pct == 50.0


def test_compute_progress_breakdown_by_category():
    tasks = [
        _make_task("A", completed=True, category="Work"),
        _make_task("B", completed=False, category="Work"),
        _make_task("C", completed=True, category="Health"),
    ]
    snapshot = compute_progress(tasks)
    assert snapshot.by_category["Work"] == {"completed": 1, "pending": 1, "total": 2}
    assert snapshot.by_category["Health"] == {"completed": 1, "pending": 0, "total": 1}


def test_get_pending_task_titles_orders_by_priority():
    tasks = [
        _make_task("Low priority", completed=False, priority="Low"),
        _make_task("High priority", completed=False, priority="High"),
        _make_task("Medium priority", completed=False, priority="Medium"),
    ]
    titles = get_pending_task_titles(tasks)
    assert titles[0] == "High priority"
    assert titles[-1] == "Low priority"


def test_get_completed_task_titles_excludes_pending():
    tasks = [
        _make_task("Done", completed=True),
        _make_task("Not done", completed=False),
    ]
    titles = get_completed_task_titles(tasks)
    assert titles == ["Done"]
