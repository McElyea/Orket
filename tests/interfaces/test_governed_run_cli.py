from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket.interfaces.orket_bundle_cli import main
from tests.application.test_governed_run_demo_service import _write_test_scenario


# Layer: integration
def test_governed_run_cli_run_inspect_and_replay(tmp_path: Path, capsys) -> None:
    """Layer: integration. Proves the CLI boundary can run, inspect, and replay a governed-run bundle."""
    scenario = _write_test_scenario(tmp_path)
    run_dir = tmp_path / ".runs" / "governed-run-test"

    assert main(["run", "scenario", str(scenario), "--workspace", str(tmp_path)]) == 0
    run_output = capsys.readouterr().out
    assert "[model] Wants to inspect files" in run_output
    assert "[orket] Allowed: read-only observation allowed" in run_output
    assert "[orket] Approval required: write operation requires human approval" in run_output
    assert "[orket] Blocked: shell command is not in the allowlist" in run_output
    assert (run_dir / "evidence.json").is_file()

    assert main(["inspect", str(run_dir)]) == 0
    inspect_output = capsys.readouterr().out
    assert "decision=requires_approval" in inspect_output
    assert "status=blocked" in inspect_output

    assert main(["replay", str(run_dir)]) == 0
    replay_output = capsys.readouterr().out
    assert "replay_status: success" in replay_output
    assert "side_effects_replayed: false" in replay_output


# Layer: integration
def test_governed_run_demo_uses_packaged_default_outside_repo(tmp_path: Path, monkeypatch, capsys) -> None:
    """Layer: integration. Proves the default governed-run scenario is not resolved from the checkout CWD."""
    monkeypatch.chdir(tmp_path)

    assert main(["demo", "governed-run", "--workspace", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "[model] Wants to inspect files" in output
    assert (tmp_path / ".runs" / "governed-run-demo" / "evidence.json").is_file()


# Layer: live_truth
@pytest.mark.end_to_end
def test_governed_run_packaged_default_via_native_process(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves the public governed-run command works outside the checkout."""
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "orket.interfaces.orket_bundle_cli",
            "demo",
            "governed-run",
            "--workspace",
            str(tmp_path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "[orket] Run completed" in result.stdout
    assert (tmp_path / ".runs" / "governed-run-demo" / "evidence.json").is_file()
