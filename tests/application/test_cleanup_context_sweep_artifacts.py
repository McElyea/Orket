from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_cleanup_context_sweep_artifacts_removes_ephemeral_storage(tmp_path: Path) -> None:
    out_dir = tmp_path / "context_sweep"
    target = out_dir / ".storage" / "context_ceilings"
    target.mkdir(parents=True, exist_ok=True)
    (target / "x.json").write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/cleanup_context_sweep_artifacts.py",
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "OK"
    assert not (out_dir / ".storage").exists()


def test_cleanup_context_sweep_artifacts_dry_run_keeps_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "context_sweep"
    target = out_dir / ".storage" / "context_ceilings"
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "python",
            "scripts/cleanup_context_sweep_artifacts.py",
            "--out-dir",
            str(out_dir),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert (out_dir / ".storage").exists()
