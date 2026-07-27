"""Unit tests for src.email_service.

These tests avoid any real network/SMTP calls - they test the pure
message-composition logic and the config-validation guard clause in
``send_email``.
"""

from __future__ import annotations

from src.email_service import build_progress_email_html, motivational_message, send_email
from src.models import ProgressSnapshot


def test_motivational_message_thresholds():
    assert "Incredible" in motivational_message(100)
    assert "almost there" in motivational_message(80)
    assert "halfway" in motivational_message(60)
    assert "Solid start" in motivational_message(30)
    assert "fresh page" in motivational_message(0)


def test_build_progress_email_html_contains_key_data():
    progress = ProgressSnapshot(
        total_tasks=4,
        completed_tasks=3,
        pending_tasks=1,
        completed_pct=75.0,
        remaining_pct=25.0,
        by_category={},
        by_priority={},
    )
    html = build_progress_email_html(
        progress=progress,
        completed_titles=["Task A", "Task B"],
        pending_titles=["Task C"],
        current_streak=5,
        send_label="9:00 AM Update",
    )
    assert "75.0%" in html
    assert "Task A" in html
    assert "Task C" in html
    assert "9:00 AM Update" in html


def test_send_email_fails_gracefully_without_config(monkeypatch):
    # validate_email_config() reads directly from src.config's module-level
    # values, so those (not email_service's imported copies) must be patched
    # to reliably exercise the "missing configuration" guard clause without
    # depending on whatever .env is present in the environment running tests.
    import src.config as config

    monkeypatch.setattr(config, "EMAIL_ADDRESS", "")
    monkeypatch.setattr(config, "EMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(config, "RECIPIENT_EMAIL", "")

    result = send_email(subject="Test", html_body="<p>Test</p>")
    assert result is False

