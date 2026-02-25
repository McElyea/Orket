from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_offline_matrix_passes_with_core_doc() -> None:
    out_path = Path("benchmarks/results/offline_matrix_check_test.json")
    result = subprocess.run(
        [
            "python",
            "scripts/check_offline_matrix.py",
            "--matrix-doc",
            "docs/projects/core-pillars/09-OFFLINE-CAPABILITY-MATRIX.md",
            "--out",
            str(out_path),
            "--require-default-offline",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["default_network_mode"] == "offline"


def test_check_offline_matrix_fails_when_doc_missing(tmp_path: Path) -> None:
    out_path = tmp_path / "offline_check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_offline_matrix.py",
            "--matrix-doc",
            str(tmp_path / "missing.md"),
            "--out",
            str(out_path),
            "--require-default-offline",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert any(item.startswith("missing_matrix_doc:") for item in payload["failures"])
