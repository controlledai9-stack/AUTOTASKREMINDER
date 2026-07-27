"""Task management: create, read, update, delete, and query tasks.

This module is the only place that writes SQL against the ``tasks`` table.
Every function returns/accepts :class:`src.models.Task` instances so callers
(the Streamlit UI, the scheduler script, tests) never have to deal with raw
``sqlite3.Row`` objects directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from src.database import get_connection
from src.models import Task, TaskStatus
from src.utils import get_logger

logger = get_logger(__name__)


def _row_to_task(row) -> Task:
    """Convert a ``sqlite3.Row`` into a :class:`Task` instance."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"] or "",
        category=row["category"] or "Other",
        priority=row["priority"] or "Medium",
        status=row["status"] or "pending",
        due_date=row["due_date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


def create_task(
    title: str,
    description: str = "",
    category: str = "Other",
    priority: str = "Medium",
    due_date: Optional[str] = None,
) -> Task:
    """Insert a new task and return the persisted :class:`Task`.

    Args:
        title: Required, non-empty task title.
        description: Optional free-text notes.
        category: Category label (e.g. "Work", "Health").
        priority: One of "Low", "Medium", "High".
        due_date: Optional ISO date string (``YYYY-MM-DD``).

    Raises:
        ValueError: If ``title`` is empty or whitespace-only.
    """
    title = title.strip()
    if not title:
        raise ValueError("Task title cannot be empty.")

    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, description, category, priority, status,
                                due_date, created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                title,
                description.strip(),
                category,
                priority,
                TaskStatus.PENDING.value,
                due_date,
                now,
                now,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
    logger.info("Created task #%s: %s", new_id, title)
    return get_task(new_id)  # type: ignore[return-value]


def get_task(task_id: int) -> Optional[Task]:
    """Fetch a single task by id, or ``None`` if it doesn't exist."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def get_all_tasks(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    search_query: Optional[str] = None,
) -> List[Task]:
    """Fetch tasks, optionally filtered by category, priority, status, or text.

    Args:
        category: Exact category match (case-sensitive), or ``None`` for all.
        priority: Exact priority match, or ``None`` for all.
        status: "pending" or "completed", or ``None`` for all.
        search_query: Case-insensitive substring match against title and
            description, or ``None``/empty to skip text filtering.

    Returns:
        Tasks ordered by priority (High first) then most recently created.
    """
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if priority and priority != "All":
        query += " AND priority = ?"
        params.append(priority)
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if search_query:
        query += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?)"
        like = f"%{search_query.lower()}%"
        params.extend([like, like])

    # Order High > Medium > Low, then newest first.
    query += """
        ORDER BY
            CASE priority
                WHEN 'High' THEN 0
                WHEN 'Medium' THEN 1
                WHEN 'Low' THEN 2
                ELSE 3
            END,
            created_at DESC
    """

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_task(row) for row in rows]


def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
) -> Optional[Task]:
    """Update one or more fields of an existing task.

    Only fields explicitly passed (not ``None``) are updated. Returns the
    updated task, or ``None`` if no task with ``task_id`` exists.
    """
    existing = get_task(task_id)
    if existing is None:
        logger.warning("Attempted to update non-existent task #%s", task_id)
        return None

    updated_title = title.strip() if title is not None else existing.title
    if not updated_title:
        raise ValueError("Task title cannot be empty.")

    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, category = ?, priority = ?,
                due_date = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated_title,
                description if description is not None else existing.description,
                category if category is not None else existing.category,
                priority if priority is not None else existing.priority,
                due_date if due_date is not None else existing.due_date,
                now,
                task_id,
            ),
        )
        conn.commit()
    logger.info("Updated task #%s", task_id)
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    """Delete a task by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Deleted task #%s", task_id)
    return deleted


def set_task_status(task_id: int, completed: bool) -> Optional[Task]:
    """Mark a task as completed or pending.

    Args:
        task_id: The task to update.
        completed: ``True`` to mark completed, ``False`` to mark pending.

    Returns:
        The updated task, or ``None`` if it doesn't exist.
    """
    existing = get_task(task_id)
    if existing is None:
        return None

    now = datetime.now().isoformat(timespec="seconds")
    new_status = TaskStatus.COMPLETED.value if completed else TaskStatus.PENDING.value
    completed_at = now if completed else None

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, completed_at, now, task_id),
        )
        conn.commit()
    logger.info("Task #%s marked %s", task_id, new_status)
    return get_task(task_id)


def delete_all_completed() -> int:
    """Delete every completed task. Returns the number of rows deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM tasks WHERE status = ?", (TaskStatus.COMPLETED.value,)
        )
        conn.commit()
    logger.info("Deleted %s completed tasks", cursor.rowcount)
    return cursor.rowcount


def get_distinct_categories() -> List[str]:
    """Return all distinct category values currently in use, sorted."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM tasks ORDER BY category"
        ).fetchall()
    return [row["category"] for row in rows]
