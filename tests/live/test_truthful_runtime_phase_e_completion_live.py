from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.orchestration.engine import OrchestrationEngine
from scripts.governance.generate_runtime_truth_evidence_package import (
    generate_runtime_truth_evidence_package,
)
from scripts.governance.run_runtime_truth_acceptance_gate import (
    evaluate_runtime_truth_acceptance_gate,
)
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model
from tests.live.test_system_acceptance_pipeline import _write_core_assets

pytestmark = pytest.mark.end_to_end


def _read_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _run_roots(workspace: Path) -> list[Path]:
    runs_root = workspace / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


@pytest.mark.asyncio
async def test_phase_e_live_acceptance_gate_and_evidence_package_closeout(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. Verifies a live provider-backed run emits Phase E governance artifacts and passes the gate."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase E proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "phase_e_live.db")
    _write_core_assets(root, epic_id="truthful_runtime_phase_e_live", environment_model=_live_model())

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("truthful_runtime_phase_e_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_root = run_roots[0]
    run_summary = _read_json(run_root / "run_summary.json")
    runtime_contracts = workspace / "observability" / run_root.name / "runtime_contracts"

    assert run_summary["status"] == "done"
    assert runtime_contracts.exists()

    conformance_governance = _read_json(runtime_contracts / "conformance_governance_contract.json")
    governance_section_ids = {row["section_id"] for row in conformance_governance["sections"]}
    assert "golden_transcript_diff_policy" in governance_section_ids
    assert "operator_signoff_bundle" in governance_section_ids
    assert "repo_introspection_report" in governance_section_ids
    assert (runtime_contracts / "workspace_state_snapshot.json").exists()
    assert (runtime_contracts / "capability_manifest.json").exists()

    gate_payload = await asyncio.to_thread(
        evaluate_runtime_truth_acceptance_gate,
        workspace=workspace.resolve(),
        run_id=run_root.name,
        check_drift=True,
    )
    assert gate_payload["ok"] is True
    assert gate_payload["details"]["conformance_governance_contract_check"]["ok"] is True
    assert gate_payload["details"]["release_confidence_scorecard_check"]["ok"] is True
    assert gate_payload["details"]["trust_language_review_check"]["ok"] is True
    assert gate_payload["details"]["workspace_hygiene_rules_check"]["ok"] is True
    assert gate_payload["details"]["spec_debt_queue_check"]["ok"] is True

    exit_code, evidence_payload, evidence_out_path = await asyncio.to_thread(
        generate_runtime_truth_evidence_package,
        workspace=workspace.resolve(),
        run_id=run_root.name,
    )
    assert exit_code == 0
    assert evidence_payload["gate_summary"]["ok"] is True
    assert evidence_payload["artifact_inventory"]["required_files_missing"] == []
    assert evidence_payload["decision_record"]["promotion_recommendation"] == "eligible"
    assert evidence_payload["decision_record"]["required_operator_action"] == "operator_signoff_required"

    written_evidence = _read_json(evidence_out_path)
    assert written_evidence["schema_version"] == "runtime_truth_evidence_package.v1"
    assert "diff_ledger" in written_evidence

    print(
        "[live][phase-e][closeout] "
        f"run_id={run_root.name} gate_ok={gate_payload['ok']} "
        f"promotion={evidence_payload['decision_record']['promotion_recommendation']} "
        f"operator_action={evidence_payload['decision_record']['required_operator_action']}"
    )
