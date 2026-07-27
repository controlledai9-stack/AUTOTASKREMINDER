"""Email building and sending via Gmail SMTP.

This module has two responsibilities:

1. Compose HTML email bodies (progress updates and weekly summaries).
2. Send them over SMTP using credentials from :mod:`src.config`.

It intentionally does not know anything about *when* to send - that
scheduling concern lives in ``scheduler/send_update.py`` and the GitHub
Actions workflow files, so this module can be reused (and unit-tested)
independently of any scheduler.
"""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from src.config import (
    EMAIL_ADDRESS,
    EMAIL_APP_PASSWORD,
    RECIPIENT_EMAIL,
    SENDER_NAME,
    SMTP_HOST,
    SMTP_PORT,
    validate_email_config,
)
from src.database import get_connection
from src.models import ProgressSnapshot
from src.utils import get_logger, now_local

logger = get_logger(__name__)


def motivational_message(completed_pct: float) -> str:
    """Return a motivational message tailored to the current progress level.

    Args:
        completed_pct: Completion percentage in the range [0, 100].
    """
    if completed_pct >= 100:
        return "Incredible work - you've completed everything on your list today! 🎉"
    if completed_pct >= 75:
        return "You're almost there! A final push and today is a clean sweep. 💪"
    if completed_pct >= 50:
        return "Great momentum - you're over halfway through today's tasks. Keep going! 🚀"
    if completed_pct >= 25:
        return "Solid start. Pick your next task and keep the momentum building. 🔥"
    if completed_pct > 0:
        return "Every task completed counts - let's build on this and keep moving. 🌱"
    return "A fresh page for today. Pick one task and just get started - momentum follows action. ✨"


def _progress_bar_html(pct: float, color: str = "#6366F1") -> str:
    """Return a small inline-CSS HTML progress bar for embedding in emails.

    Email clients strip most CSS, so this deliberately uses only inline
    ``style`` attributes and table-based layout, which is the most
    reliably-rendered approach across clients like Gmail and Outlook.
    """
    pct = max(0.0, min(100.0, pct))
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#EEF0F6;border-radius:8px;overflow:hidden;">
      <tr>
        <td width="{pct}%" style="background-color:{color};height:18px;"></td>
        <td style="height:18px;"></td>
      </tr>
    </table>
    """


def build_progress_email_html(
    progress: ProgressSnapshot,
    completed_titles: List[str],
    pending_titles: List[str],
    current_streak: int,
    send_label: str,
) -> str:
    """Build the HTML body for a scheduled progress-update email.

    Args:
        progress: The current progress snapshot.
        completed_titles: Titles of (some) completed tasks to list.
        pending_titles: Titles of (some) pending tasks to list.
        current_streak: The user's current daily streak, in days.
        send_label: Human-readable label for when this is being sent
            (e.g. "9:00 AM Update").

    Returns:
        A complete HTML document string suitable as an email body.
    """
    message = motivational_message(progress.completed_pct)
    timestamp = now_local().strftime("%A, %B %d, %Y - %I:%M %p")

    completed_list = "".join(f"<li style='margin-bottom:6px;'>✅ {t}</li>" for t in completed_titles) or (
        "<li style='color:#9CA3AF;'>No tasks completed yet</li>"
    )
    pending_list = "".join(f"<li style='margin-bottom:6px;'>⏳ {t}</li>" for t in pending_titles) or (
        "<li style='color:#9CA3AF;'>Nothing pending - you're all caught up!</li>"
    )

    return f"""
    <html>
    <body style="font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background-color:#F5F6FA; margin:0; padding:24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#6366F1,#8B5CF6);padding:28px 32px;">
            <h1 style="color:#FFFFFF;margin:0;font-size:20px;">📊 {send_label}</h1>
            <p style="color:#E0E7FF;margin:6px 0 0 0;font-size:13px;">{timestamp}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;">
            <p style="font-size:15px;color:#374151;margin-top:0;">{message}</p>

            <div style="margin:20px 0;">
              <div style="display:flex;justify-content:space-between;font-size:13px;color:#6B7280;margin-bottom:6px;">
                <span>Completed: <strong style="color:#111827;">{progress.completed_pct:.1f}%</strong></span>
                <span>Remaining: <strong style="color:#111827;">{progress.remaining_pct:.1f}%</strong></span>
              </div>
              {_progress_bar_html(progress.completed_pct)}
            </div>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
              <tr>
                <td style="text-align:center;padding:12px;background:#F0FDF4;border-radius:8px;width:33%;">
                  <div style="font-size:22px;font-weight:700;color:#16A34A;">{progress.completed_tasks}</div>
                  <div style="font-size:11px;color:#6B7280;">Completed</div>
                </td>
                <td style="width:8px;"></td>
                <td style="text-align:center;padding:12px;background:#FFF7ED;border-radius:8px;width:33%;">
                  <div style="font-size:22px;font-weight:700;color:#EA580C;">{progress.pending_tasks}</div>
                  <div style="font-size:11px;color:#6B7280;">Pending</div>
                </td>
                <td style="width:8px;"></td>
                <td style="text-align:center;padding:12px;background:#EFF6FF;border-radius:8px;width:33%;">
                  <div style="font-size:22px;font-weight:700;color:#2563EB;">🔥 {current_streak}</div>
                  <div style="font-size:11px;color:#6B7280;">Day Streak</div>
                </td>
              </tr>
            </table>

            <h3 style="font-size:13px;color:#111827;margin-bottom:8px;">Completed Today</h3>
            <ul style="padding-left:18px;margin:0 0 16px 0;font-size:13px;color:#374151;">{completed_list}</ul>

            <h3 style="font-size:13px;color:#111827;margin-bottom:8px;">Still Pending</h3>
            <ul style="padding-left:18px;margin:0;font-size:13px;color:#374151;">{pending_list}</ul>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px;background:#F9FAFB;text-align:center;">
            <p style="font-size:11px;color:#9CA3AF;margin:0;">Sent automatically by AI Daily Progress Tracker</p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def build_weekly_summary_html(
    daily_breakdown: List[dict],
    average_completion_pct: float,
    total_completed: int,
    total_tasks: int,
    current_streak: int,
    longest_streak: int,
) -> str:
    """Build the HTML body for the weekly summary email.

    Args:
        daily_breakdown: List of dicts like
            ``{"date": "2026-07-20", "completion_pct": 80.0}`` for the past
            7 days, oldest first.
        average_completion_pct: Average completion percentage over the week.
        total_completed: Total tasks completed across the week.
        total_tasks: Total tasks that existed across the week.
        current_streak: Current streak in days.
        longest_streak: Longest streak on record, in days.
    """
    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:6px 0;font-size:13px;color:#374151;">{datetime.fromisoformat(d['date']).strftime('%a, %b %d')}</td>
          <td style="padding:6px 0;text-align:right;font-size:13px;color:#111827;font-weight:600;">{d['completion_pct']:.0f}%</td>
        </tr>
        """
        for d in daily_breakdown
    )

    return f"""
    <html>
    <body style="font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background-color:#F5F6FA; margin:0; padding:24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#0EA5E9,#6366F1);padding:28px 32px;">
            <h1 style="color:#FFFFFF;margin:0;font-size:20px;">🗓️ Your Weekly Summary</h1>
            <p style="color:#E0F2FE;margin:6px 0 0 0;font-size:13px;">{now_local().strftime('%B %d, %Y')}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
              <tr>
                <td style="text-align:center;padding:12px;background:#EFF6FF;border-radius:8px;width:33%;">
                  <div style="font-size:20px;font-weight:700;color:#2563EB;">{average_completion_pct:.0f}%</div>
                  <div style="font-size:11px;color:#6B7280;">Avg. Completion</div>
                </td>
                <td style="width:8px;"></td>
                <td style="text-align:center;padding:12px;background:#F0FDF4;border-radius:8px;width:33%;">
                  <div style="font-size:20px;font-weight:700;color:#16A34A;">{total_completed}/{total_tasks}</div>
                  <div style="font-size:11px;color:#6B7280;">Tasks Done</div>
                </td>
                <td style="width:8px;"></td>
                <td style="text-align:center;padding:12px;background:#FFF7ED;border-radius:8px;width:33%;">
                  <div style="font-size:20px;font-weight:700;color:#EA580C;">🔥 {current_streak}</div>
                  <div style="font-size:11px;color:#6B7280;">Current Streak</div>
                </td>
              </tr>
            </table>

            <h3 style="font-size:13px;color:#111827;margin-bottom:8px;">Day-by-Day Completion</h3>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #F3F4F6;">
              {rows_html}
            </table>

            <p style="font-size:12px;color:#6B7280;margin-top:20px;">Longest streak on record: <strong>{longest_streak} days</strong>. Keep it up! 🏆</p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px;background:#F9FAFB;text-align:center;">
            <p style="font-size:11px;color:#9CA3AF;margin:0;">Sent automatically by AI Daily Progress Tracker</p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def send_email(subject: str, html_body: str, email_type: str = "progress_update") -> bool:
    """Send an HTML email via Gmail SMTP and log the attempt.

    Args:
        subject: Email subject line.
        html_body: Full HTML document to use as the email body.
        email_type: A short label used only in the local ``email_log``
            table for auditing (e.g. "progress_update", "weekly_summary").

    Returns:
        True if the send succeeded, False otherwise. Never raises -
        failures are caught, logged, and recorded so a scheduled run
        doesn't crash the whole GitHub Actions job.
    """
    status = validate_email_config()
    if not status.is_valid:
        logger.error(
            "Cannot send email - missing configuration: %s", ", ".join(status.missing_fields)
        )
        _log_email_attempt(email_type, RECIPIENT_EMAIL or "unknown", False, "Missing config")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{SENDER_NAME} <{EMAIL_ADDRESS}>"
    message["To"] = RECIPIENT_EMAIL
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, RECIPIENT_EMAIL, message.as_string())
        logger.info("Email sent successfully: %s", subject)
        _log_email_attempt(email_type, RECIPIENT_EMAIL, True, "")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed - check EMAIL_APP_PASSWORD")
        _log_email_attempt(email_type, RECIPIENT_EMAIL, False, "SMTP authentication failed")
        return False
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send email")
        _log_email_attempt(email_type, RECIPIENT_EMAIL, False, str(exc))
        return False


def _log_email_attempt(email_type: str, recipient: str, success: bool, detail: str) -> None:
    """Persist a record of an email send attempt for auditing purposes."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO email_log (sent_at, email_type, recipient, success, detail)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    email_type,
                    recipient,
                    int(success),
                    detail,
                ),
            )
            conn.commit()
    except Exception:  # noqa: BLE001 - logging must never itself crash the send flow
        logger.exception("Failed to write to email_log (non-fatal)")


def get_recent_email_log(limit: int = 20) -> List[dict]:
    """Return the most recent email send attempts, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM email_log ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
