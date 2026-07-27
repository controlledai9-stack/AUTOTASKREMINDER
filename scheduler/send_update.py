"""Standalone script invoked by GitHub Actions (or manually, or via cron/Task
Scheduler) to send a scheduled email.

This script deliberately does not depend on Streamlit - it only imports
from ``src/``, so it can run in a minimal GitHub Actions job with just
``pip install -r requirements.txt``.

Usage:
    python scheduler/send_update.py --type progress --label "9:00 AM Update"
    python scheduler/send_update.py --type weekly

Exit codes:
    0 - email sent successfully (or nothing to send, which is not an error)
    1 - email send failed (surfaces as a failed GitHub Actions run so you
        get notified)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure the project root is importable when this script is run directly
# (e.g. `python scheduler/send_update.py`) rather than as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import progress_calculator, streak_tracker, task_manager  # noqa: E402
from src.database import initialize_database  # noqa: E402
from src.email_service import build_progress_email_html, build_weekly_summary_html, send_email  # noqa: E402
from src.utils import get_logger, today_iso  # noqa: E402

logger = get_logger(__name__)


def send_progress_update(send_label: str) -> bool:
    """Compute current progress and send a scheduled progress-update email.

    Args:
        send_label: Human-readable label describing this send slot, e.g.
            "9:00 AM Update", used in the email subject/heading.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    all_tasks = task_manager.get_all_tasks()
    progress = progress_calculator.compute_progress(all_tasks)
    streak_tracker.record_snapshot(progress)
    current_streak = streak_tracker.compute_current_streak()

    completed_titles = progress_calculator.get_completed_task_titles(all_tasks, limit=8)
    pending_titles = progress_calculator.get_pending_task_titles(all_tasks, limit=8)

    html = build_progress_email_html(
        progress=progress,
        completed_titles=completed_titles,
        pending_titles=pending_titles,
        current_streak=current_streak,
        send_label=send_label,
    )
    subject = f"📊 {send_label}: {progress.completed_pct:.0f}% Complete Today"
    success = send_email(subject=subject, html_body=html, email_type="progress_update")

    if success:
        logger.info("Progress update sent: %.1f%% complete", progress.completed_pct)
    else:
        logger.error("Progress update failed to send")
    return success


def send_weekly_summary() -> bool:
    """Build and send the weekly summary email covering the last 7 days.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    history = streak_tracker.get_snapshot_history(limit_days=7)
    daily_breakdown = [
        {"date": s.date, "completion_pct": s.completion_pct} for s in history
    ]

    total_completed = sum(s.completed_tasks for s in history)
    total_tasks = sum(s.total_tasks for s in history)
    average_pct = (
        sum(s.completion_pct for s in history) / len(history) if history else 0.0
    )
    current_streak = streak_tracker.compute_current_streak()
    longest_streak = streak_tracker.compute_longest_streak()

    html = build_weekly_summary_html(
        daily_breakdown=daily_breakdown,
        average_completion_pct=average_pct,
        total_completed=total_completed,
        total_tasks=total_tasks,
        current_streak=current_streak,
        longest_streak=longest_streak,
    )
    subject = f"🗓️ Weekly Summary - {average_pct:.0f}% Avg. Completion"
    success = send_email(subject=subject, html_body=html, email_type="weekly_summary")

    if success:
        logger.info("Weekly summary sent: %.1f%% average completion", average_pct)
    else:
        logger.error("Weekly summary failed to send")
    return success


def main() -> int:
    """Parse CLI arguments and dispatch to the appropriate send function."""
    parser = argparse.ArgumentParser(description="Send a scheduled progress email.")
    parser.add_argument(
        "--type",
        choices=["progress", "weekly"],
        required=True,
        help="Which kind of email to send.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help='Display label for progress updates, e.g. "9:00 AM Update". '
        "Defaults to a label inferred from the current local time.",
    )
    args = parser.parse_args()

    initialize_database()

    if args.type == "progress":
        label = args.label or f"{datetime.now().strftime('%-I:%M %p')} Update"
        success = send_progress_update(label)
    else:
        success = send_weekly_summary()

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
