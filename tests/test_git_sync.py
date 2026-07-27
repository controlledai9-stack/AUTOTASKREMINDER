"""Unit tests for src.git_sync.

These tests run against a real throwaway git repository created in a temp
directory (with a local bare "remote" instead of a real GitHub push), so
they exercise the actual git plumbing without touching any real network or
real repository.
"""

from __future__ import annotations

import subprocess

import pytest

from src import git_sync


def _run(*args: str, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Set up a local repo with a local bare remote, and point git_sync at it."""
    remote_dir = tmp_path / "remote.git"
    repo_dir = tmp_path / "repo"
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True)

    subprocess.run(["git", "init", "--bare", str(remote_dir)], capture_output=True, text=True)
    subprocess.run(["git", "init", str(repo_dir)], capture_output=True, text=True)
    _run("config", "user.email", "test@example.com", cwd=repo_dir)
    _run("config", "user.name", "Test User", cwd=repo_dir)
    _run("remote", "add", "origin", str(remote_dir), cwd=repo_dir)

    (data_dir / "tracker.db").write_text("initial content")
    _run("add", "data/tracker.db", cwd=repo_dir)
    _run("commit", "-m", "initial", cwd=repo_dir)
    _run("branch", "-M", "main", cwd=repo_dir)
    _run("push", "-u", "origin", "main", cwd=repo_dir)

    monkeypatch.setattr(git_sync, "PROJECT_ROOT", repo_dir)
    return repo_dir


def test_is_git_repository_true_for_real_repo(fake_repo):
    assert git_sync.is_git_repository() is True


def test_is_git_repository_false_outside_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(git_sync, "PROJECT_ROOT", tmp_path)
    assert git_sync.is_git_repository() is False


def test_sync_with_no_changes_reports_nothing_to_sync(fake_repo):
    result = git_sync.sync_database_to_github()
    assert result.success is True
    assert "Nothing to sync" in result.message


def test_sync_with_local_changes_pushes_successfully(fake_repo):
    db_path = fake_repo / "data" / "tracker.db"
    db_path.write_text("updated content with a new task")

    result = git_sync.sync_database_to_github()
    assert result.success is True
    assert "Synced" in result.message

    # Confirm it actually reached the "remote".
    log = _run("log", "--oneline", "-1", cwd=fake_repo)
    assert "sync local task changes" in log.stdout


def test_status_summary_detects_pending_changes(fake_repo):
    db_path = fake_repo / "data" / "tracker.db"
    db_path.write_text("a change nobody has synced yet")

    status = git_sync.get_git_status_summary()
    assert status.success is True
    assert "ready to sync" in status.message


def test_sync_auto_recovers_when_remote_has_new_commit(fake_repo, tmp_path):
    """Reproduces the reported bug: a GitHub Actions run pushes its own
    commit (e.g. streak/log data) to the remote in between the user's last
    pull and their sync click. The old behavior surfaced a raw
    '[rejected] ... fetch first' error; sync should now recover
    automatically via fetch + rebase and still get the user's change onto
    GitHub.
    """
    remote_url = _run("remote", "get-url", "origin", cwd=fake_repo).stdout.strip()

    # Simulate a second clone (standing in for the GitHub Actions runner)
    # committing and pushing a change of its own.
    ci_clone = tmp_path / "ci_clone"
    subprocess.run(["git", "clone", remote_url, str(ci_clone)], capture_output=True, text=True)
    _run("checkout", "main", cwd=ci_clone)
    _run("config", "user.email", "ci@example.com", cwd=ci_clone)
    _run("config", "user.name", "CI Bot", cwd=ci_clone)
    (ci_clone / "data" / "tracker.db").write_text("ci-updated streak data")
    _run("add", "data/tracker.db", cwd=ci_clone)
    _run("commit", "-m", "chore: update tracker data [skip ci]", cwd=ci_clone)
    push = _run("push", cwd=ci_clone)
    assert push.returncode == 0

    # Now the user's local repo (fake_repo) is behind the remote. They make
    # a local change and sync - this should NOT surface a raw rejection.
    (fake_repo / "data" / "tracker.db").write_text("user's new task")
    result = git_sync.sync_database_to_github()

    assert result.success is True
    assert "kept" in result.message

    # Confirm both changes actually made it to the remote.
    verify_clone = tmp_path / "verify_clone"
    subprocess.run(["git", "clone", remote_url, str(verify_clone)], capture_output=True, text=True)
    _run("checkout", "main", cwd=verify_clone)
    log = _run("log", "--oneline", "-5", cwd=verify_clone)
    assert "sync local task changes" in log.stdout
    assert "update tracker data" in log.stdout
