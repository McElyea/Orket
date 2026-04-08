from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

import orket.application.review.run_service as run_service_module
import orket.application.review.snapshot_loader as snapshot_loader_module
from orket.application.review.errors import ReviewError

pytestmark = pytest.mark.unit


def test_snapshot_loader_git_timeout_raises_structured_review_error(monkeypatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies snapshot git timeouts fail fast with command context."""

    def timed_out(command, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["timeout"] == snapshot_loader_module.GIT_COMMAND_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd=command, timeout=60, stderr=b"slow")

    monkeypatch.setattr(snapshot_loader_module.subprocess, "run", timed_out)

    started = time.monotonic()
    with pytest.raises(ReviewError) as exc_info:
        snapshot_loader_module._run_git(tmp_path, ["diff", "--name-status", "base", "head"])

    assert time.monotonic() - started < 1
    assert exc_info.value.command == ["git", "diff", "--name-status", "base", "head"]
    assert exc_info.value.stderr == "slow"
    assert "timed out" in str(exc_info.value)


def test_review_run_git_paths_timeout_raises_structured_review_error(monkeypatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies review path discovery git timeouts fail fast with command context."""

    def timed_out(command, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["timeout"] == run_service_module.GIT_COMMAND_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd=command, timeout=60, stderr="slow")

    monkeypatch.setattr(run_service_module.subprocess, "run", timed_out)

    started = time.monotonic()
    with pytest.raises(ReviewError) as exc_info:
        run_service_module._git_paths(tmp_path, "base", "head")

    assert time.monotonic() - started < 1
    assert exc_info.value.command == ["git", "diff", "--name-only", "base", "head"]
    assert exc_info.value.stderr == "slow"
    assert "timed out" in str(exc_info.value)
