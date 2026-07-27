"""CSV export utilities for tasks and streak history."""

from __future__ import annotations

import csv
import io
from typing import List

from src.models import DailySnapshot, Task


def tasks_to_csv(tasks: List[Task]) -> str:
    """Serialize a list of tasks into CSV text.

    Returns:
        A CSV-formatted string (with header row) ready to be offered as a
        file download.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "ID",
            "Title",
            "Description",
            "Category",
            "Priority",
            "Status",
            "Due Date",
            "Created At",
            "Completed At",
        ]
    )
    for task in tasks:
        writer.writerow(
            [
                task.id,
                task.title,
                task.description,
                task.category,
                task.priority,
                task.status,
                task.due_date or "",
                task.created_at,
                task.completed_at or "",
            ]
        )
    return buffer.getvalue()


def snapshots_to_csv(snapshots: List[DailySnapshot]) -> str:
    """Serialize daily progress snapshots into CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Completed Tasks", "Total Tasks", "Completion %"])
    for snap in snapshots:
        writer.writerow([snap.date, snap.completed_tasks, snap.total_tasks, snap.completion_pct])
    return buffer.getvalue()
