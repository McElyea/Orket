from __future__ import annotations

import json
from pathlib import Path

from scripts.extensions.compare_controller_replay_parity import main


def _payload(*, status: str, error_code: str | None) -> dict:
    child_status = "success" if status == "success" else "failed"
    obs_status = "success" if child_status == "success" else "failure"
    return {
        "controller_summary": {
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "status": status,
            "error_code": error_code,
            "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
            "enforced_caps": {"max_depth": 1, "max_fanout": 5, "child_timeout_seconds": 30},
            "child_results": [
                {
                    "target_workload": "sdk_child_a_v1",
                    "status": child_status,
                    "requested_timeout": 30,
                    "enforced_timeout": 30,
                    "normalized_error": error_code,
                    "summary": {"ok": child_status == "success"},
                }
            ],
        },
        "controller_observability_projection": [
            {"event": "controller_run", "result": status, "error_code": error_code},
            {"event": "controller_child", "child_index": 0, "status": obs_status, "error_code": error_code},
        ],
    }


def test_compare_controller_replay_parity_writes_diff_ledger_report(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    actual_path = tmp_path / "actual.json"
    out_path = tmp_path / "parity_report.json"
    expected_path.write_text(json.dumps(_payload(status="success", error_code=None), indent=2), encoding="utf-8")
    actual_path.write_text(json.dumps(_payload(status="success", error_code=None), indent=2), encoding="utf-8")

    exit_code = main(
        [
            "--expected",
            str(expected_path),
            "--actual",
            str(actual_path),
            "--out",
            str(out_path),
            "--strict",
        ]
    )
    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["parity_ok"] is True
    assert isinstance(report.get("diff_ledger"), list)


def test_compare_controller_replay_parity_strict_fails_on_mismatch(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    actual_path = tmp_path / "actual.json"
    expected_path.write_text(json.dumps(_payload(status="success", error_code=None), indent=2), encoding="utf-8")
    actual_path.write_text(
        json.dumps(_payload(status="failed", error_code="controller.child_execution_failed"), indent=2), encoding="utf-8"
    )

    exit_code = main(
        [
            "--expected",
            str(expected_path),
            "--actual",
            str(actual_path),
            "--strict",
        ]
    )
    assert exit_code == 1
