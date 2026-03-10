from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.governance import generate_runtime_truth_evidence_package as generator


def _mock_gate_payload() -> dict[str, object]:
    return {
        "schema_version": "runtime_truth_acceptance_gate.v1",
        "ok": True,
        "failures": [],
        "details": {
            "drift_report": {
                "schema_version": "1.0",
                "ok": True,
                "checks": [],
            }
        },
    }


# Layer: contract
def test_build_runtime_truth_evidence_package_contains_required_sections(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(generator, "evaluate_runtime_truth_acceptance_gate", lambda **kwargs: _mock_gate_payload())
    monkeypatch.setattr(generator, "evaluate_release_confidence_scorecard", lambda: {"ok": True, "dimension_count": 5})
    monkeypatch.setattr(generator, "evaluate_non_fatal_error_budget", lambda: {"ok": True, "budget_count": 4})
    monkeypatch.setattr(generator, "evaluate_interface_freeze_windows", lambda: {"ok": True, "window_count": 3})
    monkeypatch.setattr(generator, "evaluate_promotion_rollback_criteria", lambda: {"ok": True, "trigger_count": 3})

    payload = generator.build_runtime_truth_evidence_package(
        workspace=tmp_path,
        run_id="run-evidence",
        now=datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC),
    )
    assert payload["schema_version"] == "runtime_truth_evidence_package.v1"
    assert payload["run_id"] == "run-evidence"
    assert payload["gate_summary"]["ok"] is True
    assert payload["decision_record"]["promotion_recommendation"] == "eligible"
    assert "drift_report" in payload
    assert "artifact_inventory" in payload


# Layer: integration
def test_generate_runtime_truth_evidence_package_writes_diff_ledger_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(generator, "evaluate_runtime_truth_acceptance_gate", lambda **kwargs: _mock_gate_payload())
    monkeypatch.setattr(generator, "evaluate_release_confidence_scorecard", lambda: {"ok": True, "dimension_count": 5})
    monkeypatch.setattr(generator, "evaluate_non_fatal_error_budget", lambda: {"ok": True, "budget_count": 4})
    monkeypatch.setattr(generator, "evaluate_interface_freeze_windows", lambda: {"ok": True, "window_count": 3})
    monkeypatch.setattr(generator, "evaluate_promotion_rollback_criteria", lambda: {"ok": True, "trigger_count": 3})

    out_path = tmp_path / "runtime_truth_evidence_package.json"
    exit_code, payload, resolved_out_path = generator.generate_runtime_truth_evidence_package(
        workspace=tmp_path,
        run_id="run-evidence",
        out_path=out_path,
        now=datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC),
    )
    assert exit_code == 0
    assert payload["gate_summary"]["ok"] is True
    written = json.loads(resolved_out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "runtime_truth_evidence_package.v1"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(generator, "evaluate_runtime_truth_acceptance_gate", lambda **kwargs: _mock_gate_payload())
    monkeypatch.setattr(generator, "evaluate_release_confidence_scorecard", lambda: {"ok": True, "dimension_count": 5})
    monkeypatch.setattr(generator, "evaluate_non_fatal_error_budget", lambda: {"ok": True, "budget_count": 4})
    monkeypatch.setattr(generator, "evaluate_interface_freeze_windows", lambda: {"ok": True, "window_count": 3})
    monkeypatch.setattr(generator, "evaluate_promotion_rollback_criteria", lambda: {"ok": True, "trigger_count": 3})

    out_path = tmp_path / "runtime_truth_evidence_package.json"
    exit_code = generator.main(["--workspace", str(tmp_path), "--run-id", "run-evidence", "--out", str(out_path)])
    assert exit_code == 0
