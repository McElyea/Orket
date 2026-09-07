from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = PROJECT_ROOT / "main.py"


def _run_main(
    workspace: Path,
    *args: str,
    durable_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    env["ORKET_DURABLE_ROOT"] = str(durable_root or workspace / ".orket" / "durable")
    env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run(
        [sys.executable, str(MAIN_PATH), *args],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _run_installed_runtime(
    workspace: Path,
    *args: str,
    durable_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    env["ORKET_DURABLE_ROOT"] = str(durable_root or workspace / ".orket" / "durable")
    env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run(
        [sys.executable, "-m", "orket.cli", "runtime", *args],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


# Layer: live_truth
@pytest.mark.end_to_end
def test_installed_runtime_help_exits_zero_from_fresh_workspace(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves the installed command root exposes truthful runtime help."""
    result = _run_installed_runtime(tmp_path, "--help")

    assert result.returncode == 0
    assert "usage: orket runtime" in result.stdout
    assert "--card" in result.stdout
    assert "orket runtime --card initialize_orket" in result.stdout
    assert "python main.py" not in result.stdout + result.stderr
    assert (tmp_path / ".orket" / "durable" / "config" / "user_settings.json").is_file()


# Layer: live_truth
@pytest.mark.end_to_end
def test_installed_runtime_known_fatal_exits_nonzero(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves handled runtime failure propagates through the installed command root."""
    result = _run_installed_runtime(tmp_path, "extensions", "unsupported")

    assert result.returncode == 1
    assert "[FATAL]" in result.stdout
    assert "orket runtime extensions list" in result.stdout
    assert "SettingsBridgeError" not in result.stdout + result.stderr


# Layer: live_truth
@pytest.mark.end_to_end
def test_installed_runtime_invalid_named_card_exits_nonzero(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves runtime arguments reach the card parser and failures stay nonzero."""
    result = _run_installed_runtime(
        tmp_path,
        "--card",
        "card-that-does-not-exist",
        "--workspace",
        str(tmp_path),
    )

    assert result.returncode == 1
    assert "[CRITICAL ERROR]" in result.stdout


# Layer: live_truth
@pytest.mark.end_to_end
def test_main_help_exits_zero_from_fresh_workspace(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves native help succeeds through the real main.py process."""
    result = _run_main(tmp_path, "--help")

    assert result.returncode == 0
    assert "--card" in result.stdout
    assert "SettingsBridgeError" not in result.stdout + result.stderr


# Layer: live_truth
@pytest.mark.end_to_end
def test_main_known_fatal_exits_nonzero_after_first_run_setup(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves fresh onboarding persists and a handled fatal error exits nonzero."""
    result = _run_main(tmp_path, "extensions", "unsupported")

    assert result.returncode == 1
    assert "[FIRST RUN]" in result.stdout
    assert "[FATAL]" in result.stdout
    assert "SettingsBridgeError" not in result.stdout + result.stderr
    assert (tmp_path / ".orket" / "durable" / "config" / "user_settings.json").is_file()


# Layer: live_truth
@pytest.mark.end_to_end
def test_main_first_run_persistence_failure_exits_nonzero_without_success_claim(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves failed first-run persistence is fatal and emits no success narration."""
    blocked_root = tmp_path / "durable-root-is-a-file"
    blocked_root.write_text("not a directory", encoding="utf-8")

    result = _run_main(tmp_path, "--help", durable_root=blocked_root)

    assert result.returncode == 1
    assert "[FATAL]" in result.stdout
    assert "[FIRST RUN]" not in result.stdout


# Layer: live_truth
@pytest.mark.end_to_end
def test_main_invalid_named_card_exits_nonzero(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves an invalid named card cannot return process success."""
    result = _run_main(
        tmp_path,
        "--card",
        "card-that-does-not-exist",
        "--workspace",
        str(tmp_path),
    )

    assert result.returncode == 1
    assert "[CRITICAL ERROR]" in result.stdout
