"""Helpers for syncing the local SQLite database to GitHub from within the
Streamlit app itself.

This exists because GitHub Actions can only see task data that has been
committed and pushed to the repository (see docs/ARCHITECTURE.md). Rather
than requiring the user to leave the app and run git commands manually
every time, this module wraps the same ``git add / commit / push`` sequence
as :file:`scripts/sync_db.sh` so it can be triggered by a button in the UI.

All git commands run against the project root (two levels up from this
file) via ``subprocess``, with the working directory pinned explicitly so
this works regardless of what directory Streamlit itself was launched
from.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import List

from src.config import PROJECT_ROOT
from src.utils import get_logger

logger = get_logger(__name__)

# Relative to PROJECT_ROOT - the one file we sync. Kept as a constant so
# this module and scripts/sync_db.sh agree on exactly what gets committed.
TRACKED_DB_RELATIVE_PATH = "data/tracker.db"


@dataclass
class SyncResult:
    """Outcome of a sync attempt, with enough detail to show the user why
    it failed if it did."""

    success: bool
    message: str
    details: List[str] = field(default_factory=list)


def _run_git(*args: str) -> subprocess.CompletedProcess:
    """Run a git command in the project root and return the completed process.

    Never raises on a non-zero exit code - callers inspect ``returncode``
    themselves, since "nothing to commit" and similar are expected,
    non-error outcomes in this workflow.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def is_git_repository() -> bool:
    """Whether PROJECT_ROOT is inside a git repository at all."""
    result = _run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0


def get_git_status_summary() -> SyncResult:
    """Return a human-readable summary of the current git state, for display
    in the UI before the user clicks "Sync" - helps diagnose issues like
    "not a git repo" or "no remote configured" up front.
    """
    if not is_git_repository():
        return SyncResult(
            success=False,
            message="This folder is not a git repository.",
            details=[
                "Make sure you're running `streamlit run app.py` from inside "
                "the same folder where you ran `git init` / `git clone`.",
            ],
        )

    remote = _run_git("remote", "-v")
    if not remote.stdout.strip():
        return SyncResult(
            success=False,
            message="No git remote is configured.",
            details=["Add one with: git remote add origin <your-repo-url>"],
        )

    branch = _run_git("branch", "--show-current")
    status = _run_git("status", "--porcelain", TRACKED_DB_RELATIVE_PATH)

    has_local_changes = bool(status.stdout.strip())
    return SyncResult(
        success=True,
        message=(
            f"On branch '{branch.stdout.strip()}'. "
            + (
                "Local task changes are ready to sync."
                if has_local_changes
                else "Nothing to sync - GitHub already has your latest tasks."
            )
        ),
        details=[remote.stdout.strip()],
    )


def sync_database_to_github(commit_message: str = "chore: sync local task changes") -> SyncResult:
    """Commit and push data/tracker.db, mirroring scripts/sync_db.sh.

    Returns:
        SyncResult with ``success=True`` if the push completed (including
        the case where there was nothing new to push), or ``success=False``
        with diagnostic details if any step failed.
    """
    if not is_git_repository():
        return SyncResult(
            success=False,
            message="Not a git repository - can't sync.",
            details=[
                "Run this app from inside the folder you cloned/initialized "
                "with git, and make sure a GitHub remote is configured.",
            ],
        )

    add_result = _run_git("add", TRACKED_DB_RELATIVE_PATH)
    if add_result.returncode != 0:
        return SyncResult(
            success=False,
            message="git add failed.",
            details=[add_result.stderr.strip()],
        )

    staged_result = _run_git("diff", "--cached", "--name-only", TRACKED_DB_RELATIVE_PATH)
    if not staged_result.stdout.strip():
        return SyncResult(
            success=True,
            message="Nothing to sync - GitHub already has your latest tasks.",
        )

    commit_result = _run_git("commit", "-m", commit_message)
    if commit_result.returncode != 0:
        return SyncResult(
            success=False,
            message="git commit failed.",
            details=[commit_result.stdout.strip(), commit_result.stderr.strip()],
        )

    return _push_with_rebase_retry()


_NON_FAST_FORWARD_MARKERS = ("[rejected]", "fetch first", "non-fast-forward")


def _push_with_rebase_retry() -> SyncResult:
    """Push the current branch, automatically recovering from the common
    "remote has commits you don't have" case.

    This happens routinely with this project's setup: a GitHub Actions run
    (e.g. a scheduled email) can commit its own update to data/tracker.db
    (streak/log data) at any time, including between when you last pulled
    and when you click "Sync". Rather than surfacing a raw git error for
    that expected situation, this fetches the remote change and merges it
    in automatically, then retries the push once.

    data/tracker.db is a binary SQLite file, so a line-based merge (or
    rebase) essentially always conflicts the moment both sides have
    touched it - there's no meaningful way to combine two binary blobs
    byte-by-byte. Rather than leaving the repo in a conflicted state that
    needs manual resolution every time, this resolves any such conflict by
    keeping the *local* copy of tracker.db (``-X ours``): your just-synced
    task changes are the reason you clicked "Sync", so they take priority.
    Anything the remote had (streak/log rows written by a scheduled run)
    that isn't reflected locally is regenerated automatically the next
    time an email is sent, since those tables are recomputed from live
    task data on every run - so nothing meaningful is permanently lost.
    """
    first_attempt = _run_git("push")
    if first_attempt.returncode == 0:
        logger.info("Synced data/tracker.db to GitHub")
        return SyncResult(
            success=True,
            message="Synced! Your latest tasks are now on GitHub and ready for the next scheduled email.",
        )

    stderr = first_attempt.stderr.strip()
    if not any(marker in stderr for marker in _NON_FAST_FORWARD_MARKERS):
        # Some other failure (auth, no access, network, etc.) - not something
        # a merge can fix.
        return SyncResult(
            success=False,
            message="git push failed - your commit was made locally but did not reach GitHub.",
            details=[
                stderr,
                "Common causes: not signed in / no push access to this repo, "
                "or a network issue.",
            ],
        )

    # The remote moved ahead of us (most often: a GitHub Actions run
    # committed streak/log data). Pull it in, favoring our local task
    # changes if the two collide, and retry.
    logger.info("Push rejected (remote has new commits) - fetching and merging before retry")
    branch = _run_git("branch", "--show-current").stdout.strip() or "main"

    fetch_result = _run_git("fetch", "origin")
    if fetch_result.returncode != 0:
        return SyncResult(
            success=False,
            message="git push was rejected, and the automatic git fetch to recover also failed.",
            details=[stderr, fetch_result.stderr.strip(), "Try running `git pull` manually."],
        )

    merge_result = _run_git(
        "merge",
        f"origin/{branch}",
        "-X",
        "ours",
        "-m",
        "chore: merge remote update (auto-resolved in favor of local task changes)",
    )
    if merge_result.returncode != 0:
        _run_git("merge", "--abort")
        return SyncResult(
            success=False,
            message=(
                "GitHub had changes that couldn't be automatically combined with yours. "
                "Your local commit is safe but not yet pushed."
            ),
            details=[
                merge_result.stdout.strip(),
                merge_result.stderr.strip(),
                "Resolve manually: `git pull` (or `git fetch && git merge origin/" + branch + "`), "
                "resolve the conflict in data/tracker.db, then `git push`.",
            ],
        )

    second_attempt = _run_git("push")
    if second_attempt.returncode != 0:
        return SyncResult(
            success=False,
            message="Merged successfully, but the retry push still failed.",
            details=[second_attempt.stderr.strip()],
        )

    logger.info("Synced data/tracker.db to GitHub (after auto merge)")
    return SyncResult(
        success=True,
        message=(
            "Synced! GitHub had a newer update (likely from a scheduled email run) - your task "
            "changes were kept and both are now pushed."
        ),
    )
