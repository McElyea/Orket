# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.run_failure_replay_harness import (
    evaluate_failure_replay_harness,
    main,
    run_failure_replay_harness,
)


# Layer: contract
def test_evaluate_failure_replay_harness_reports_clean_parity(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    payload = {
        "runtime_contract_hash": "abc123",
        "status": "ok",
        "operations": ["tool.call", "tool.result"],
    }
    baseline.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")

    report = evaluate_failure_replay_harness(
        baseline_path=baseline,
        candidate_path=candidate,
        max_differences=200,
    )
    assert report["ok"] is True
    assert report["difference_count"] == 0
    assert report["path"] == "primary"


# Layer: integration
def test_run_failure_replay_harness_writes_diff_ledger_payload(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps({"runtime_contract_hash": "abc123", "status": "ok"}, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps({"runtime_contract_hash": "xyz999", "status": "ok"}, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "failure_replay_harness_report.json"
    exit_code, payload = run_failure_replay_harness(
        baseline_path=baseline,
        candidate_path=candidate,
        out_path=out_path,
        max_differences=200,
    )
    assert exit_code == 2
    assert payload["ok"] is False
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "failure_replay_harness.v1"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success_on_matching_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    payload = {"runtime_contract_hash": "abc123", "status": "ok"}
    baseline.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    out_path = tmp_path / "failure_replay_harness_report.json"
    exit_code = main(
        [
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--out",
            str(out_path),
        ]
    )
    assert exit_code == 0
