# LIFECYCLE: live
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.techdebt.run_recurring_maintenance_cycle import main, run_cycle


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _runner_factory(*, fail_key: str | None = None):
    def _runner(argv: list[str] | tuple[str, ...], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        command = " ".join(str(token) for token in argv)
        if "check_td03052026_gate_audit.py" in command:
            return subprocess.CompletedProcess(argv, 0, stdout="TD03052026 gate audit passed.\n", stderr="")
        if "check_docs_project_hygiene.py" in command:
            if fail_key == "docs_project_hygiene":
                return subprocess.CompletedProcess(
                    argv,
                    1,
                    stdout="Docs project hygiene check failed:\n- missing roadmap path\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="Docs project hygiene check passed.\n",
                stderr="",
            )
        if fail_key == "pytest":
            return subprocess.CompletedProcess(argv, 1, stdout="1 failed, 1820 passed in 2.00s\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="1821 passed, 9 skipped in 1.23s\n", stderr="")

    return _runner


# Layer: contract
def test_run_recurring_maintenance_cycle_writes_cycle_artifacts_and_report(tmp_path: Path) -> None:
    cycle_root = tmp_path / "cycle-root"
    report_root = tmp_path / "reports"
    readiness_out = tmp_path / "readiness" / "readiness_checklist.json"

    exit_code = run_cycle(
        [
            "--cycle-id",
            "2026-03-07_cycle-a",
            "--cycle-root-base",
            str(cycle_root),
            "--report-root",
            str(report_root),
            "--readiness-out",
            str(readiness_out),
            "--section-d-note",
            "Checklist reviewed with no curation changes required.",
        ],
        runner=_runner_factory(),
    )

    assert exit_code == 0
    cycle_dir = cycle_root / "2026-03-07_cycle-a"
    result_path = cycle_dir / "result.json"
    report_path = report_root / "techdebt_recurring_cycle_2026-03-07_a_report.json"
    environment_path = cycle_dir / "environment.json"

    assert (cycle_dir / "commands.txt").exists()
    assert environment_path.exists()
    assert (cycle_dir / "stdout.log").exists()
    assert (cycle_dir / "stderr.log").exists()
    assert result_path.exists()
    assert report_path.exists()

    result_payload = _load_json(result_path)
    report_payload = _load_json(report_path)
    environment_payload = _load_json(environment_path)

    assert result_payload["status"] == "pass"
    assert result_payload["sections_executed"] == ["A", "D"]
    assert result_payload["evidence"]["tracked_artifact"] == readiness_out.as_posix()
    assert report_payload["cycle_id"] == "2026-03-07_cycle-a"
    assert report_payload["evidence"]["results"]["pytest"] == "PASS (1821 passed, 9 skipped in 1.23s)"
    assert "diff_ledger" in result_payload
    assert "diff_ledger" in report_payload
    assert "diff_ledger" in environment_payload


# Layer: contract
def test_run_recurring_maintenance_cycle_strict_fails_when_required_check_is_red(tmp_path: Path) -> None:
    cycle_root = tmp_path / "cycle-root"
    report_root = tmp_path / "reports"
    readiness_out = tmp_path / "readiness" / "readiness_checklist.json"

    exit_code = run_cycle(
        [
            "--cycle-id",
            "2026-03-07_cycle-b",
            "--cycle-root-base",
            str(cycle_root),
            "--report-root",
            str(report_root),
            "--readiness-out",
            str(readiness_out),
            "--strict",
        ],
        runner=_runner_factory(fail_key="docs_project_hygiene"),
    )

    assert exit_code == 1
    payload = _load_json(cycle_root / "2026-03-07_cycle-b" / "result.json")
    assert payload["status"] == "fail"
    assert payload["sections"]["A"]["status"] == "FAIL"
    assert payload["evidence"]["results"]["docs_project_hygiene"].startswith("FAIL")


# Layer: unit
def test_run_recurring_maintenance_cycle_rejects_invalid_cycle_id() -> None:
    exit_code = main(["--cycle-id", "bad/name"])
    assert exit_code == 2
