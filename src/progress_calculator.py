"""Derives progress and completion statistics from a list of tasks.

Kept separate from :mod:`task_manager` so the math (percentages,
breakdowns by category/priority) can be unit-tested in isolation from the
database, and reused identically by the Streamlit UI and the email
scheduler.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from src.models import ProgressSnapshot, Task


def compute_progress(tasks: List[Task]) -> ProgressSnapshot:
    """Compute a :class:`ProgressSnapshot` for the given tasks.

    Args:
        tasks: The full set of tasks to summarize (typically "today's"
            tasks, or all tasks, depending on the caller's intent).

    Returns:
        A ProgressSnapshot with totals, percentages, and breakdowns by
        category and priority. If ``tasks`` is empty, percentages are 0.0
        rather than raising a division error.
    """
    total = len(tasks)
    completed = sum(1 for t in tasks if t.is_completed)
    pending = total - completed

    completed_pct = round((completed / total) * 100, 1) if total else 0.0
    remaining_pct = round(100.0 - completed_pct, 1) if total else 0.0

    by_category = _breakdown_by_field(tasks, "category")
    by_priority = _breakdown_by_field(tasks, "priority")

    return ProgressSnapshot(
        total_tasks=total,
        completed_tasks=completed,
        pending_tasks=pending,
        completed_pct=completed_pct,
        remaining_pct=remaining_pct,
        by_category=by_category,
        by_priority=by_priority,
    )


def _breakdown_by_field(tasks: List[Task], field_name: str) -> Dict[str, Dict[str, int]]:
    """Group tasks by an attribute and count completed/pending within each group.

    Args:
        tasks: Tasks to group.
        field_name: Name of the Task attribute to group by (e.g. "category").

    Returns:
        A dict like ``{"Work": {"completed": 3, "pending": 2, "total": 5}}``.
    """
    groups: Dict[str, Dict[str, int]] = {}
    for task in tasks:
        key = getattr(task, field_name)
        bucket = groups.setdefault(key, {"completed": 0, "pending": 0, "total": 0})
        bucket["total"] += 1
        if task.is_completed:
            bucket["completed"] += 1
        else:
            bucket["pending"] += 1
    return groups


def get_pending_task_titles(tasks: List[Task], limit: int = 10) -> List[str]:
    """Return titles of pending tasks (highest priority first), capped at ``limit``."""
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    pending = [t for t in tasks if not t.is_completed]
    pending.sort(key=lambda t: priority_order.get(t.priority, 3))
    return [t.title for t in pending[:limit]]


def get_completed_task_titles(tasks: List[Task], limit: int = 10) -> List[str]:
    """Return titles of completed tasks, most recently completed first."""
    completed = [t for t in tasks if t.is_completed]
    completed.sort(key=lambda t: t.completed_at or "", reverse=True)
    return [t.title for t in completed[:limit]]


def category_counts(tasks: List[Task]) -> Counter:
    """Simple count of tasks per category, useful for chart rendering."""
    return Counter(t.category for t in tasks)


def priority_counts(tasks: List[Task]) -> Counter:
    """Simple count of tasks per priority level, useful for chart rendering."""
    return Counter(t.priority for t in tasks)
