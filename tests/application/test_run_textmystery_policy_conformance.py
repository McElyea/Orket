from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _init_fake_textmystery_tests(root: Path, *, should_pass: bool) -> None:
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    body = "def test_gate():\n    assert True\n" if should_pass else "def test_gate():\n    assert False\n"
    (tests_dir / "test_policy_gate.py").write_text(body, encoding="utf-8")


def test_run_textmystery_policy_conformance_pass(tmp_path: Path) -> None:
    repo = tmp_path / "textmystery_repo"
    _init_fake_textmystery_tests(repo, should_pass=True)
    output = tmp_path / "policy_report.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_textmystery_policy_conformance.py",
            "--textmystery-root",
            str(repo),
            "--test",
            "tests/test_policy_gate.py",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "textmystery_policy_conformance.v1"
    assert payload["status"] == "pass"
    assert payload["run"]["returncode"] == 0


def test_run_textmystery_policy_conformance_fail(tmp_path: Path) -> None:
    repo = tmp_path / "textmystery_repo"
    _init_fake_textmystery_tests(repo, should_pass=False)
    output = tmp_path / "policy_report.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_textmystery_policy_conformance.py",
            "--textmystery-root",
            str(repo),
            "--test",
            "tests/test_policy_gate.py",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["run"]["returncode"] != 0
