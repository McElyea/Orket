from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _check(status: str) -> dict:
    return {"status": status}


def test_build_explorer_check_summary_passes(tmp_path: Path) -> None:
    ingestion = tmp_path / "ingestion.json"
    rollup = tmp_path / "rollup.json"
    guards = tmp_path / "guards.json"
    out = tmp_path / "summary.json"
    ingestion.write_text(json.dumps(_check("PASS")) + "\n", encoding="utf-8")
    rollup.write_text(json.dumps(_check("PASS")) + "\n", encoding="utf-8")
    guards.write_text(json.dumps(_check("SKIP")) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/build_explorer_check_summary.py",
            "--ingestion",
            str(ingestion),
            "--rollup",
            str(rollup),
            "--guards",
            str(guards),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["statuses"]["guards"] == "SKIP"


def test_build_explorer_check_summary_fails_on_failed_check(tmp_path: Path) -> None:
    ingestion = tmp_path / "ingestion.json"
    rollup = tmp_path / "rollup.json"
    guards = tmp_path / "guards.json"
    out = tmp_path / "summary.json"
    ingestion.write_text(json.dumps(_check("PASS")) + "\n", encoding="utf-8")
    rollup.write_text(json.dumps(_check("FAIL")) + "\n", encoding="utf-8")
    guards.write_text(json.dumps(_check("PASS")) + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            "python",
            "scripts/build_explorer_check_summary.py",
            "--ingestion",
            str(ingestion),
            "--rollup",
            str(rollup),
            "--guards",
            str(guards),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
