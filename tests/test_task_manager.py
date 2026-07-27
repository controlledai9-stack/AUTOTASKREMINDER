"""Unit tests for src.task_manager."""

from __future__ import annotations

import pytest

from src import task_manager


def test_create_task_persists_fields():
    task = task_manager.create_task(
        title="Write tests", description="For the tracker", category="Work", priority="High"
    )
    assert task.id is not None
    assert task.title == "Write tests"
    assert task.category == "Work"
    assert task.priority == "High"
    assert task.status == "pending"


def test_create_task_rejects_empty_title():
    with pytest.raises(ValueError):
        task_manager.create_task(title="   ")


def test_get_task_returns_none_for_missing_id():
    assert task_manager.get_task(9999) is None


def test_update_task_changes_only_given_fields():
    task = task_manager.create_task(title="Original", category="Work", priority="Low")
    updated = task_manager.update_task(task.id, title="Updated title")
    assert updated.title == "Updated title"
    assert updated.category == "Work"  # unchanged
    assert updated.priority == "Low"  # unchanged


def test_update_task_rejects_empty_title():
    task = task_manager.create_task(title="Keep me")
    with pytest.raises(ValueError):
        task_manager.update_task(task.id, title="   ")


def test_set_task_status_marks_completed_and_pending():
    task = task_manager.create_task(title="Toggle me")
    completed = task_manager.set_task_status(task.id, True)
    assert completed.status == "completed"
    assert completed.completed_at is not None

    pending_again = task_manager.set_task_status(task.id, False)
    assert pending_again.status == "pending"
    assert pending_again.completed_at is None


def test_delete_task_removes_row():
    task = task_manager.create_task(title="Delete me")
    assert task_manager.delete_task(task.id) is True
    assert task_manager.get_task(task.id) is None
    assert task_manager.delete_task(task.id) is False  # already gone


def test_get_all_tasks_filters_by_status_and_category():
    task_manager.create_task(title="Work task", category="Work")
    t2 = task_manager.create_task(title="Health task", category="Health")
    task_manager.set_task_status(t2.id, True)

    work_only = task_manager.get_all_tasks(category="Work")
    assert len(work_only) == 1
    assert work_only[0].category == "Work"

    completed_only = task_manager.get_all_tasks(status="completed")
    assert len(completed_only) == 1
    assert completed_only[0].title == "Health task"


def test_get_all_tasks_search_matches_title_and_description():
    task_manager.create_task(title="Buy groceries", description="milk, eggs, bread")
    task_manager.create_task(title="Call dentist", description="reschedule appointment")

    results = task_manager.get_all_tasks(search_query="milk")
    assert len(results) == 1
    assert results[0].title == "Buy groceries"


def test_delete_all_completed_only_removes_completed():
    t1 = task_manager.create_task(title="Done task")
    task_manager.create_task(title="Not done task")
    task_manager.set_task_status(t1.id, True)

    removed = task_manager.delete_all_completed()
    assert removed == 1
    remaining = task_manager.get_all_tasks()
    assert len(remaining) == 1
    assert remaining[0].title == "Not done task"
