import json
from pathlib import Path

import pytest

from orket.exceptions import ExecutionFailed
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_epic_assets(root: Path, epic_id: str) -> None:
    _write_json(
        root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Run ledger test",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_run_ledger_records_incomplete_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_incomplete")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-02-13/sess-ledger-incomplete",
            "commit": "abc123",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    await pipeline.run_epic(
        "ledger_epic_incomplete",
        build_id="build-ledger-epic-incomplete",
        session_id="sess-ledger-incomplete",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-incomplete")
    assert ledger is not None
    assert ledger["status"] == "incomplete"
    assert ledger["failure_class"] is None
    assert ledger["failure_reason"] is None
    assert ledger["summary_json"]["session_status"] == "incomplete"
    assert ledger["summary_json"]["status_counts"]["ready"] == 1
    assert ledger["artifact_json"]["workspace"] == str(workspace)
    assert ledger["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert ledger["artifact_json"]["gitea_export"]["commit"] == "abc123"


@pytest.mark.asyncio
async def test_run_ledger_records_failed_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_failed")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _raise_execute_epic(**_kwargs):
        raise ExecutionFailed("forced failure for ledger")

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-02-13/sess-ledger-failed",
            "commit": "def456",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _raise_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    with pytest.raises(ExecutionFailed, match="forced failure for ledger"):
        await pipeline.run_epic(
            "ledger_epic_failed",
            build_id="build-ledger-epic-failed",
            session_id="sess-ledger-failed",
        )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-failed")
    assert ledger is not None
    assert ledger["status"] == "failed"
    assert ledger["failure_class"] == "ExecutionFailed"
    assert "forced failure for ledger" in (ledger["failure_reason"] or "")
    assert ledger["summary_json"]["session_status"] == "failed"
    assert ledger["summary_json"]["status_counts"]["ready"] == 1
    assert ledger["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert ledger["artifact_json"]["gitea_export"]["commit"] == "def456"

    runs = await pipeline.sessions.get_recent_runs(limit=5)
    failed_run = next((r for r in runs if r["id"] == "sess-ledger-failed"), None)
    assert failed_run is not None
    assert failed_run["status"] == "failed"


@pytest.mark.asyncio
async def test_run_ledger_records_terminal_failure_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_terminal_failure")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _blocked_execute_epic(**_kwargs):
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED)
        return None

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-02-14/sess-ledger-terminal-failure",
            "commit": "xyz789",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _blocked_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    await pipeline.run_epic(
        "ledger_epic_terminal_failure",
        build_id="build-ledger-epic-terminal-failure",
        session_id="sess-ledger-terminal-failure",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-terminal-failure")
    assert ledger is not None
    assert ledger["status"] == "terminal_failure"
    assert ledger["summary_json"]["session_status"] == "terminal_failure"
    assert ledger["summary_json"]["status_counts"]["blocked"] == 1


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_records_runtime_contract_bootstrap_artifacts(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_contract_bootstrap")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _no_export_run(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _no_export_run)

    await pipeline.run_epic(
        "ledger_epic_contract_bootstrap",
        build_id="build-ledger-epic-contract-bootstrap",
        session_id="sess-ledger-contract-bootstrap",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-contract-bootstrap")
    assert ledger is not None
    artifact_json = ledger["artifact_json"]
    assert artifact_json["tool_registry_snapshot"]["tool_registry_version"] == "1.2.0"
    assert artifact_json["artifact_schema_snapshot"]["artifact_schema_registry_version"] == "1.0"
    assert len(artifact_json["tool_contract_snapshot"]["tool_contracts"]) >= 1
    assert artifact_json["compatibility_map_schema_snapshot"]["schema_version"] == "1.0"
    assert artifact_json["compatibility_map_snapshot"]["mapping_count"] >= 1
    assert artifact_json["run_identity"]["run_id"] == "sess-ledger-contract-bootstrap"
    assert artifact_json["run_identity"]["workload"] == "ledger_epic_contract_bootstrap"
    assert artifact_json["run_determinism_class"] == "workspace"
    assert artifact_json["run_phase_contract"]["schema_version"] == "1.0"
    assert artifact_json["run_phase_contract"]["entry_phase"] == "input_normalize"
    assert artifact_json["run_phase_contract"]["terminal_phase"] == "emit_observability"
    assert artifact_json["runtime_status_vocabulary"]["schema_version"] == "1.0"
    assert "running" in artifact_json["runtime_status_vocabulary"]["runtime_status_terms"]
    assert artifact_json["degradation_taxonomy"]["schema_version"] == "1.0"
    assert artifact_json["fail_behavior_registry"]["schema_version"] == "1.0"
    assert artifact_json["provider_truth_table"]["schema_version"] == "1.0"
    provider_rows = artifact_json["provider_truth_table"]["providers"]
    assert [row["provider"] for row in provider_rows] == ["ollama", "openai_compat", "lmstudio"]
    assert artifact_json["state_transition_registry"]["schema_version"] == "1.0"
    transition_domains = artifact_json["state_transition_registry"]["domains"]
    assert [row["domain"] for row in transition_domains] == ["session", "run", "tool_invocation", "voice", "ui"]
    assert artifact_json["timeout_semantics_contract"]["schema_version"] == "1.0"
    timeout_surfaces = artifact_json["timeout_semantics_contract"]["timeout_surfaces"]
    assert [row["surface"] for row in timeout_surfaces] == [
        "local_model_completion_timeout",
        "model_stream_provider_timeout",
        "model_stream_turn_timeout",
        "provider_runtime_inventory_timeout",
    ]
    assert artifact_json["streaming_semantics_contract"]["schema_version"] == "1.0"
    assert artifact_json["streaming_semantics_contract"]["terminal_events"] == ["error", "stopped"]
    assert artifact_json["runtime_truth_contract_drift_report"]["schema_version"] == "1.0"
    assert artifact_json["runtime_truth_contract_drift_report"]["ok"] is True
    assert artifact_json["runtime_truth_trace_ids"]["schema_version"] == "1.0"
    trace_artifacts = [row["artifact"] for row in artifact_json["runtime_truth_trace_ids"]["trace_ids"]]
    assert "run_phase_contract" in trace_artifacts
    assert "route_decision_artifact" in trace_artifacts
    assert artifact_json["runtime_invariant_registry"]["schema_version"] == "1.0"
    invariant_ids = [row["invariant_id"] for row in artifact_json["runtime_invariant_registry"]["invariants"]]
    assert "INV-001" in invariant_ids
    assert artifact_json["runtime_config_ownership_map"]["schema_version"] == "1.0"
    config_keys = [row["config_key"] for row in artifact_json["runtime_config_ownership_map"]["rows"]]
    assert "ORKET_STATE_BACKEND_MODE" in config_keys
    assert "ORKET_PROVIDER_QUARANTINE" in config_keys
    assert artifact_json["unknown_input_policy"]["schema_version"] == "1.0"
    unknown_surfaces = [row["surface"] for row in artifact_json["unknown_input_policy"]["surfaces"]]
    assert "provider_runtime_target.requested_provider" in unknown_surfaces
    assert artifact_json["deterministic_mode_contract"]["schema_version"] == "1.0"
    assert artifact_json["deterministic_mode_contract"]["deterministic_mode_enabled"] is False
    assert artifact_json["deterministic_mode_contract"]["resolution_source"] == "default"
    assert artifact_json["route_decision_artifact"]["schema_version"] == "1.0"
    assert artifact_json["route_decision_artifact"]["route_target"] == "epic"
    assert artifact_json["route_decision_artifact"]["reason_code"] == "default_epic_route"
    assert artifact_json["route_decision_artifact"]["deterministic_mode_enabled"] is False
    assert artifact_json["capability_manifest"]["run_id"] == "sess-ledger-contract-bootstrap"
    assert artifact_json["workspace_state_snapshot"]["workspace_type"] == "filesystem"
    assert len(str(artifact_json["workspace_state_snapshot"]["workspace_hash"])) == 64
    assert Path(artifact_json["tool_registry_snapshot_path"]).exists()
    assert Path(artifact_json["artifact_schema_snapshot_path"]).exists()
    assert Path(artifact_json["tool_contract_snapshot_path"]).exists()
    assert Path(artifact_json["compatibility_map_snapshot_path"]).exists()
    assert Path(artifact_json["run_identity_path"]).exists()
    assert Path(artifact_json["run_phase_contract_path"]).exists()
    assert Path(artifact_json["runtime_status_vocabulary_path"]).exists()
    assert Path(artifact_json["degradation_taxonomy_path"]).exists()
    assert Path(artifact_json["fail_behavior_registry_path"]).exists()
    assert Path(artifact_json["provider_truth_table_path"]).exists()
    assert Path(artifact_json["state_transition_registry_path"]).exists()
    assert Path(artifact_json["timeout_semantics_contract_path"]).exists()
    assert Path(artifact_json["streaming_semantics_contract_path"]).exists()
    assert Path(artifact_json["runtime_truth_contract_drift_report_path"]).exists()
    assert Path(artifact_json["runtime_truth_trace_ids_path"]).exists()
    assert Path(artifact_json["runtime_invariant_registry_path"]).exists()
    assert Path(artifact_json["runtime_config_ownership_map_path"]).exists()
    assert Path(artifact_json["unknown_input_policy_path"]).exists()
    assert Path(artifact_json["capability_manifest_path"]).exists()
    assert Path(artifact_json["workspace_state_snapshot_path"]).exists()


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_keeps_run_identity_immutable_across_same_session_reentry(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_identity_immutable")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _no_export_run(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _no_export_run)

    await pipeline.run_epic(
        "ledger_epic_identity_immutable",
        build_id="build-ledger-epic-identity-immutable-1",
        session_id="sess-ledger-identity-immutable",
    )
    first = await pipeline.run_ledger.get_run("sess-ledger-identity-immutable")
    assert first is not None
    first_identity = dict(first["artifact_json"]["run_identity"])

    await pipeline.run_epic(
        "ledger_epic_identity_immutable",
        build_id="build-ledger-epic-identity-immutable-2",
        session_id="sess-ledger-identity-immutable",
    )
    second = await pipeline.run_ledger.get_run("sess-ledger-identity-immutable")
    assert second is not None
    second_identity = dict(second["artifact_json"]["run_identity"])

    assert second_identity == first_identity
