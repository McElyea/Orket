from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_context_sweep_outputs_passes_with_complete_coverage(tmp_path: Path) -> None:
    for context in (4096, 8192):
        (tmp_path / f"context_{context}.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    ceiling = tmp_path / "context_ceiling.json"
    ceiling.write_text(
        json.dumps({"points": [{"context": 4096}, {"context": 8192}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_sweep_outputs.py",
            "--contexts",
            "4096,8192",
            "--summary-template",
            str(tmp_path / "context_{context}.json"),
            "--context-ceiling",
            str(ceiling),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_check_context_sweep_outputs_fails_with_missing_files(tmp_path: Path) -> None:
    (tmp_path / "context_4096.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_sweep_outputs.py",
            "--contexts",
            "4096,8192",
            "--summary-template",
            str(tmp_path / "context_{context}.json"),
            "--context-ceiling",
            str(tmp_path / "context_ceiling.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert "MISSING_CONTEXT_SUMMARY_FILES" in payload["failures"]
