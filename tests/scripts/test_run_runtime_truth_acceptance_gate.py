from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.run_runtime_truth_acceptance_gate import (
    REQUIRED_RUNTIME_CONTRACT_FILES,
    evaluate_runtime_truth_acceptance_gate,
    main,
)


def _write_contract_set(workspace: Path, run_id: str) -> Path:
    contracts_dir = workspace / "observability" / run_id / "runtime_contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_RUNTIME_CONTRACT_FILES:
        (contracts_dir / filename).write_text(
            json.dumps({"schema_version": "1.0"}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return contracts_dir


# Layer: integration
def test_runtime_truth_acceptance_gate_passes_with_drift_and_contract_files(tmp_path: Path) -> None:
    _write_contract_set(tmp_path, "run-ok")
    exit_code = main(["--workspace", str(tmp_path), "--run-id", "run-ok"])
    assert exit_code == 0


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_required_contract_file_missing(tmp_path: Path) -> None:
    contracts_dir = _write_contract_set(tmp_path, "run-missing")
    (contracts_dir / REQUIRED_RUNTIME_CONTRACT_FILES[0]).unlink()

    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="run-missing",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_contract_files_missing" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_can_run_drift_check_without_run_id(tmp_path: Path) -> None:
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=True,
    )
    assert payload["ok"] is True
    assert payload["details"]["drift_report"]["ok"] is True
    assert payload["details"]["unreachable_branch_check"]["ok"] is True
    assert payload["details"]["noop_critical_path_check"]["ok"] is True
    assert payload["details"]["environment_parity_check"]["ok"] is True
    assert payload["details"]["structured_warning_policy_check"]["ok"] is True
    assert payload["details"]["retry_classification_policy_check"]["ok"] is True
    assert payload["details"]["runtime_boundary_audit_check"]["ok"] is True
    assert payload["details"]["model_profile_bios_check"]["ok"] is True
    assert payload["details"]["interrupt_semantics_policy_check"]["ok"] is True
    assert payload["details"]["idempotency_discipline_policy_check"]["ok"] is True
    assert payload["details"]["artifact_provenance_block_policy_check"]["ok"] is True


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_unreachable_branch_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_unreachable_branches",
        lambda *, roots: {
            "schema_version": "1.0",
            "ok": False,
            "findings": [{"path": "x.py", "line": 1}],
            "parse_errors": [],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "unreachable_branch_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_noop_critical_path_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_noop_critical_paths",
        lambda *, roots: {
            "schema_version": "1.0",
            "ok": False,
            "findings": [{"path": "x.py", "line": 1, "name": "noop"}],
            "parse_errors": [],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "noop_critical_path_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_environment_parity_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_environment_parity_checklist",
        lambda *, environment, required_keys: {
            "schema_version": "1.0",
            "ok": False,
            "checks": [{"check": "required_env_keys_present", "ok": False}],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "environment_parity_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_warning_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_structured_warning_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "warning_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "structured_warning_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_retry_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_retry_classification_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "signal_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "retry_classification_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_boundary_audit_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_runtime_boundary_audit_checklist",
        lambda *, workspace: {
            "schema_version": "1.0",
            "ok": False,
            "boundary_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_boundary_audit_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_model_profile_bios_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_model_profile_bios",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "profile_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "model_profile_bios_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_interrupt_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_interrupt_semantics_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "interrupt_semantics_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_idempotency_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_idempotency_discipline_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "idempotency_discipline_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_artifact_provenance_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_artifact_provenance_block_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "required_field_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "artifact_provenance_block_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_required_file_list_tracks_new_contract_artifacts() -> None:
    assert "runtime_invariant_registry.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "runtime_config_ownership_map.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "unknown_input_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "clock_time_authority_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "capability_fallback_hierarchy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "model_profile_bios.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "interrupt_semantics_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "idempotency_discipline_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "artifact_provenance_block_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
