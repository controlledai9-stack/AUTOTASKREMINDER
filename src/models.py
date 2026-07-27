"""Typed data structures shared across the application.

Using dataclasses (rather than passing raw dicts/tuples around) gives us
type hints, autocompletion, and a single source of truth for the shape of
a "Task" or a "Progress" snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """Lifecycle status of a task."""

    PENDING = "pending"
    COMPLETED = "completed"


class Priority(str, Enum):
    """Priority levels a task can be assigned."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class Task:
    """Represents a single actionable task tracked by the user.

    Attributes:
        id: Primary key (``None`` until persisted).
        title: Short, human-readable summary of the task.
        description: Optional longer description / notes.
        category: Free-form category label (e.g. "Work", "Health").
        priority: One of :class:`Priority`.
        status: One of :class:`TaskStatus`.
        due_date: Optional ISO date string (``YYYY-MM-DD``) the task is due.
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of the last update.
        completed_at: ISO timestamp of completion, if completed.
    """

    id: Optional[int]
    title: str
    description: str = ""
    category: str = "Other"
    priority: str = Priority.MEDIUM.value
    status: str = TaskStatus.PENDING.value
    due_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    completed_at: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        """Whether the task is currently marked as completed."""
        return self.status == TaskStatus.COMPLETED.value


@dataclass
class ProgressSnapshot:
    """A computed summary of progress across a set of tasks.

    All percentage fields are expressed as floats in the range [0, 100].
    """

    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    completed_pct: float
    remaining_pct: float
    by_category: dict
    by_priority: dict


@dataclass
class DailySnapshot:
    """A persisted record of a single day's final progress.

    Used by the streak tracker to compute current/longest streaks without
    needing to recompute historical progress from raw task rows.
    """

    date: str  # ISO date, YYYY-MM-DD
    completed_tasks: int
    total_tasks: int
    completion_pct: float
