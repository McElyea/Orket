from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime import run_start_artifacts
from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: unit
def test_capture_run_start_artifacts_writes_required_run_start_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "a.txt").parent.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    payload = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-1",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    assert payload["run_identity"]["run_id"] == "run-1"
    assert payload["run_identity"]["workload"] == "core_epic"
    assert payload["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")
    assert payload["run_determinism_class"] == "workspace"
    assert payload["run_phase_contract"]["schema_version"] == "1.0"
    assert payload["run_phase_contract"]["entry_phase"] == "input_normalize"
    assert payload["run_phase_contract"]["terminal_phase"] == "emit_observability"
    assert payload["runtime_status_vocabulary"]["schema_version"] == "1.0"
    assert "terminal_failure" in payload["runtime_status_vocabulary"]["runtime_status_terms"]
    assert payload["degradation_taxonomy"]["schema_version"] == "1.0"
    assert payload["fail_behavior_registry"]["schema_version"] == "1.0"
    assert payload["provider_truth_table"]["schema_version"] == "1.0"
    providers = [row["provider"] for row in payload["provider_truth_table"]["providers"]]
    assert providers == ["ollama", "openai_compat", "lmstudio"]
    assert payload["state_transition_registry"]["schema_version"] == "1.0"
    transition_domains = [row["domain"] for row in payload["state_transition_registry"]["domains"]]
    assert transition_domains == ["session", "run", "tool_invocation", "voice", "ui"]
    assert payload["timeout_semantics_contract"]["schema_version"] == "1.0"
    timeout_surfaces = [row["surface"] for row in payload["timeout_semantics_contract"]["timeout_surfaces"]]
    assert timeout_surfaces == [
        "local_model_completion_timeout",
        "model_stream_provider_timeout",
        "model_stream_turn_timeout",
        "provider_runtime_inventory_timeout",
    ]
    assert payload["streaming_semantics_contract"]["schema_version"] == "1.0"
    assert payload["streaming_semantics_contract"]["terminal_events"] == ["error", "stopped"]
    assert payload["runtime_truth_contract_drift_report"]["schema_version"] == "1.0"
    assert payload["runtime_truth_contract_drift_report"]["ok"] is True
    assert payload["runtime_truth_trace_ids"]["schema_version"] == "1.0"
    trace_artifacts = [row["artifact"] for row in payload["runtime_truth_trace_ids"]["trace_ids"]]
    assert "run_phase_contract" in trace_artifacts
    assert "route_decision_artifact" in trace_artifacts
    assert payload["runtime_invariant_registry"]["schema_version"] == "1.0"
    invariant_ids = [row["invariant_id"] for row in payload["runtime_invariant_registry"]["invariants"]]
    assert "INV-001" in invariant_ids
    assert payload["runtime_config_ownership_map"]["schema_version"] == "1.0"
    config_keys = [row["config_key"] for row in payload["runtime_config_ownership_map"]["rows"]]
    assert "ORKET_STATE_BACKEND_MODE" in config_keys
    assert "ORKET_PROVIDER_QUARANTINE" in config_keys
    assert payload["unknown_input_policy"]["schema_version"] == "1.0"
    unknown_surfaces = [row["surface"] for row in payload["unknown_input_policy"]["surfaces"]]
    assert "provider_runtime_target.requested_provider" in unknown_surfaces
    assert payload["clock_time_authority_policy"]["schema_version"] == "1.0"
    assert payload["clock_time_authority_policy"]["defaults"]["clock_mode"] == "wall"
    assert payload["capability_fallback_hierarchy"]["schema_version"] == "1.0"
    assert payload["capability_fallback_hierarchy"]["fallback_hierarchy"]["streaming"][0]["provider"] == "ollama"
    assert Path(payload["run_identity_path"]).exists()
    assert Path(payload["run_phase_contract_path"]).exists()
    assert Path(payload["runtime_status_vocabulary_path"]).exists()
    assert Path(payload["degradation_taxonomy_path"]).exists()
    assert Path(payload["fail_behavior_registry_path"]).exists()
    assert Path(payload["provider_truth_table_path"]).exists()
    assert Path(payload["state_transition_registry_path"]).exists()
    assert Path(payload["timeout_semantics_contract_path"]).exists()
    assert Path(payload["streaming_semantics_contract_path"]).exists()
    assert Path(payload["runtime_truth_contract_drift_report_path"]).exists()
    assert Path(payload["runtime_truth_trace_ids_path"]).exists()
    assert Path(payload["runtime_invariant_registry_path"]).exists()
    assert Path(payload["runtime_config_ownership_map_path"]).exists()
    assert Path(payload["unknown_input_policy_path"]).exists()
    assert Path(payload["clock_time_authority_policy_path"]).exists()
    assert Path(payload["capability_fallback_hierarchy_path"]).exists()
    assert Path(payload["ledger_event_schema_path"]).exists()
    assert Path(payload["capability_manifest_schema_path"]).exists()
    assert Path(payload["capability_manifest_path"]).exists()
    assert Path(payload["compatibility_map_snapshot_path"]).exists()
    assert Path(payload["workspace_state_snapshot_path"]).exists()
    workspace_snapshot = payload["workspace_state_snapshot"]
    assert workspace_snapshot["workspace_type"] == "filesystem"
    assert workspace_snapshot["workspace_path"] == str(workspace.resolve())
    assert workspace_snapshot["file_count"] == 1
    assert len(str(workspace_snapshot["workspace_hash"])) == 64


# Layer: contract
def test_capture_run_start_artifacts_reuses_existing_run_identity_for_same_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    second = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 18, 0, 0, tzinfo=UTC),
    )

    assert first["run_identity"] == second["run_identity"]
    assert first["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_identity_workload_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-mismatch",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="E_RUN_IDENTITY_IMMUTABLE:workload_mismatch"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-mismatch",
            workload="other_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_phase_contract_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-phase-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    run_phase_contract_path = (
        workspace
        / "observability"
        / "run-phase-immutable"
        / "runtime_contracts"
        / "run_phase_contract.json"
    )
    run_phase_contract_path.write_text(
        '{"schema_version":"999.0","entry_phase":"route","terminal_phase":"persist","canonical_phase_order":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PHASE_CONTRACT_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-phase-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_runtime_status_vocabulary_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-status-vocab-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    runtime_status_vocabulary_path = (
        workspace
        / "observability"
        / "run-status-vocab-immutable"
        / "runtime_contracts"
        / "runtime_status_vocabulary.json"
    )
    runtime_status_vocabulary_path.write_text(
        '{"schema_version":"999.0","runtime_status_terms":["running"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STATUS_VOCABULARY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-status-vocab-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_provider_truth_table_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-provider-truth-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    provider_truth_table_path = (
        workspace
        / "observability"
        / "run-provider-truth-immutable"
        / "runtime_contracts"
        / "provider_truth_table.json"
    )
    provider_truth_table_path.write_text(
        '{"schema_version":"999.0","providers":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PROVIDER_TRUTH_TABLE_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-provider-truth-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_state_transition_registry_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-state-transition-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    state_transition_registry_path = (
        workspace
        / "observability"
        / "run-state-transition-immutable"
        / "runtime_contracts"
        / "state_transition_registry.json"
    )
    state_transition_registry_path.write_text(
        '{"schema_version":"999.0","domains":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STATE_TRANSITION_REGISTRY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-state-transition-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_streaming_semantics_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-streaming-semantics-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    streaming_semantics_path = (
        workspace
        / "observability"
        / "run-streaming-semantics-immutable"
        / "runtime_contracts"
        / "streaming_semantics_contract.json"
    )
    streaming_semantics_path.write_text(
        '{"schema_version":"999.0","event_trace_order":[],"terminal_events":[],"rules":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STREAMING_SEMANTICS_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-streaming-semantics-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_clock_time_authority_policy_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-clock-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    clock_policy_path = (
        workspace
        / "observability"
        / "run-clock-policy-immutable"
        / "runtime_contracts"
        / "clock_time_authority_policy.json"
    )
    clock_policy_path.write_text(
        '{"schema_version":"999.0","defaults":{"clock_mode":"artifact_replay"}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_CLOCK_TIME_AUTHORITY_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-clock-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_capability_fallback_hierarchy_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-fallback-hierarchy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    fallback_hierarchy_path = (
        workspace
        / "observability"
        / "run-fallback-hierarchy-immutable"
        / "runtime_contracts"
        / "capability_fallback_hierarchy.json"
    )
    fallback_hierarchy_path.write_text(
        '{"schema_version":"999.0","fallback_hierarchy":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_CAPABILITY_FALLBACK_HIERARCHY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-fallback-hierarchy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_truth_contract_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(
        run_start_artifacts,
        "runtime_truth_contract_drift_report",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "checks": [
                {
                    "check": "provider_truth_table_vs_provider_choices",
                    "ok": False,
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="E_RUN_TRUTH_CONTRACT_DRIFT"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-truth-drift",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
        )
