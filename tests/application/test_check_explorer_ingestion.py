from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_explorer_ingestion_passes_for_complete_index(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "rows": [
                    {"kind": "frontier", "schema_version": "explorer.frontier.v1", "provenance_ref": "r"},
                    {"kind": "context", "schema_version": "explorer.context_ceiling.v1", "provenance_ref": "r"},
                    {"kind": "thermal", "schema_version": "explorer.thermal_stability.v1", "provenance_ref": "r"},
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_explorer_ingestion.py", "--index", str(index)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_check_explorer_ingestion_fails_on_missing_fields(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "rows": [
                    {"kind": "frontier", "schema_version": "", "provenance_ref": "r"},
                    {"kind": "context", "schema_version": "explorer.context_ceiling.v1", "provenance_ref": ""},
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_explorer_ingestion.py", "--index", str(index)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert any("MISSING_REQUIRED_KINDS" in failure for failure in payload["failures"])


def test_check_explorer_ingestion_fixture_regression_cases(tmp_path: Path) -> None:
    valid_fixture = Path("tests/fixtures/explorer_index/valid_index.json")
    invalid_fixture = Path("tests/fixtures/explorer_index/invalid_missing_kind.json")

    valid_run = subprocess.run(
        ["python", "scripts/check_explorer_ingestion.py", "--index", str(valid_fixture)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid_run.returncode == 0, valid_run.stdout + "\n" + valid_run.stderr

    invalid_run = subprocess.run(
        ["python", "scripts/check_explorer_ingestion.py", "--index", str(invalid_fixture)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid_run.returncode == 2
