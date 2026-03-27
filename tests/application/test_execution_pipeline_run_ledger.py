import asyncio
import json
from pathlib import Path

import pytest

import orket.runtime.execution_pipeline as execution_pipeline_module
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.workflows.protocol_hashing import hash_framed_fields
from orket.exceptions import ExecutionFailed
from orket.logging import log_event
from orket.application.workflows.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from orket.naming import sanitize_name
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.runtime.run_summary import PACKET1_MISSING_TOKEN
from orket.runtime.run_summary_artifact_provenance import normalize_artifact_provenance_facts
from orket.schema import CardStatus


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _write_epic_assets(root: Path, epic_id: str, *, truthful_runtime: dict | None = None) -> None:
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
            "params": {"truthful_runtime": truthful_runtime} if truthful_runtime else {},
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


def _write_protocol_write_receipts(
    workspace: Path,
    *,
    session_id: str,
    rows: list[tuple[str, str, int, str, str]],
) -> None:
    for issue_id, role_name, turn_index, artifact_path, operation_id in rows:
        resolved_artifact_path = workspace / artifact_path
        resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_artifact_path.write_text(f"artifact:{artifact_path}", encoding="utf-8")
        manifest = build_tool_invocation_manifest(run_id=session_id, tool_name="write_file")
        tool_args = {"path": artifact_path, "content": f"artifact:{artifact_path}"}
        receipt_path = (
            workspace
            / "observability"
            / session_id
            / issue_id
            / f"{turn_index:03d}_{role_name}"
            / "protocol_receipts.log"
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_payload = {
            "run_id": session_id,
            "step_id": f"{issue_id}:{turn_index}",
            "operation_id": operation_id,
            "tool": "write_file",
            "tool_index": 0,
            "tool_args": tool_args,
            "execution_result": {"ok": True, "path": str(resolved_artifact_path)},
            "tool_invocation_manifest": manifest,
            "tool_call_hash": compute_tool_call_hash(
                tool_name="write_file",
                tool_args=tool_args,
                tool_contract_version=str(manifest["tool_contract_version"]),
                capability_profile=str(manifest["capability_profile"]),
            ),
        }
        existing = ""
        if receipt_path.exists():
            existing = receipt_path.read_text(encoding="utf-8")
            if existing and not existing.endswith("\n"):
                existing += "\n"
        receipt_path.write_text(existing + json.dumps(receipt_payload) + "\n", encoding="utf-8")


def _write_protocol_receipt(
    workspace: Path,
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    tool: str,
    tool_args: dict[str, object],
    execution_result: dict[str, object],
    operation_id: str,
    materialize_artifact: bool = True,
) -> None:
    artifact_path = str(tool_args.get("path") or execution_result.get("path") or "").strip()
    if materialize_artifact and tool == "write_file" and artifact_path:
        resolved_artifact_path = workspace / artifact_path
        resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if "content" in tool_args:
            resolved_artifact_path.write_text(str(tool_args.get("content") or ""), encoding="utf-8")
    manifest = build_tool_invocation_manifest(run_id=session_id, tool_name=tool)
    receipt_path = (
        workspace
        / "observability"
        / session_id
        / issue_id
        / f"{turn_index:03d}_{role_name}"
        / "protocol_receipts.log"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_payload = {
        "run_id": session_id,
        "step_id": f"{issue_id}:{turn_index}",
        "operation_id": operation_id,
        "tool": tool,
        "tool_index": 0,
        "tool_args": dict(tool_args),
        "execution_result": dict(execution_result),
        "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name=tool,
            tool_args=dict(tool_args),
            tool_contract_version=str(manifest["tool_contract_version"]),
            capability_profile=str(manifest["capability_profile"]),
        ),
    }
    existing = ""
    if receipt_path.exists():
        existing = receipt_path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    receipt_path.write_text(existing + json.dumps(receipt_payload) + "\n", encoding="utf-8")


def _write_legacy_turn_artifact(
    workspace: Path,
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    tool: str,
    tool_args: dict[str, object],
    execution_result: dict[str, object],
    materialize_artifact: bool = True,
) -> None:
    artifact_path = str(tool_args.get("path") or execution_result.get("path") or "").strip()
    if materialize_artifact and tool == "write_file" and artifact_path:
        resolved_artifact_path = workspace / artifact_path
        resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_artifact_path.write_text(str(tool_args.get("content") or ""), encoding="utf-8")
    turn_dir = workspace / "observability" / session_id / issue_id / f"{turn_index:03d}_{role_name}"
    turn_dir.mkdir(parents=True, exist_ok=True)
    parsed_tool_calls_path = turn_dir / "parsed_tool_calls.json"
    parsed_tool_calls = []
    if parsed_tool_calls_path.exists():
        parsed_tool_calls = json.loads(parsed_tool_calls_path.read_text(encoding="utf-8"))
    parsed_tool_calls.append({"tool": tool, "args": dict(tool_args)})
    parsed_tool_calls_path.write_text(json.dumps(parsed_tool_calls), encoding="utf-8")
    replay_key = hash_framed_fields("tool_replay_key", [tool, dict(tool_args)])[:12]
    (turn_dir / f"tool_result_{sanitize_name(tool)}_{replay_key}.json").write_text(
        json.dumps(dict(execution_result)),
        encoding="utf-8",
    )


def _log_successful_write_file(
    workspace: Path,
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    artifact_path: str,
    operation_id: str,
) -> None:
    resolved_artifact_path = workspace / artifact_path
    resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_artifact_path.write_text(f"artifact:{artifact_path}", encoding="utf-8")
    log_event(
        "tool_call_start",
        {
            "issue_id": issue_id,
            "role": role_name,
            "session_id": session_id,
            "turn_index": turn_index,
            "tool": "write_file",
            "args": {"path": artifact_path, "content": f"artifact:{artifact_path}"},
            "operation_id": operation_id,
        },
        workspace=workspace,
    )
    log_event(
        "tool_call_result",
        {
            "issue_id": issue_id,
            "role": role_name,
            "session_id": session_id,
            "turn_index": turn_index,
            "tool": "write_file",
            "ok": True,
            "error": None,
            "operation_id": operation_id,
        },
        workspace=workspace,
    )


@pytest.mark.asyncio
async def test_run_ledger_records_incomplete_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_incomplete")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
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
    _write_json(
        workspace / "agent_output" / "verification" / "runtime_verification.json",
        {"ok": True, "command_results": []},
    )

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
    assert ledger["summary_json"]["run_id"] == "sess-ledger-incomplete"
    assert ledger["summary_json"]["status"] == "incomplete"
    assert ledger["summary_json"]["failure_reason"] is None
    assert ledger["summary_json"]["duration_ms"] >= 0
    assert ledger["summary_json"]["control_plane"]["projection_source"] == "control_plane_records"
    assert ledger["summary_json"]["control_plane"]["projection_only"] is True
    assert ledger["summary_json"]["control_plane"]["run_id"] == ledger["artifact_json"]["control_plane_run_record"]["run_id"]
    assert ledger["summary_json"]["control_plane"]["run_state"] == "waiting_on_observation"
    assert ledger["summary_json"]["control_plane"]["attempt_id"] == ledger["artifact_json"]["control_plane_attempt_record"]["attempt_id"]
    assert ledger["summary_json"]["control_plane"]["attempt_state"] == "attempt_waiting"
    assert ledger["summary_json"]["control_plane"]["step_id"] == ledger["artifact_json"]["control_plane_step_record"]["step_id"]
    packet1 = ledger["summary_json"]["truthful_runtime_packet1"]
    assert packet1["provenance"]["primary_output_kind"] == "artifact"
    assert packet1["classification"]["truth_classification"] == "direct"
    assert packet1["packet1_conformance"]["status"] == "conformant"
    assert "gitea_export" not in ledger["summary_json"]["artifact_ids"]
    assert ledger["artifact_json"]["workspace"] == str(workspace)
    assert ledger["artifact_json"]["run_summary"] == ledger["summary_json"]
    summary_path = Path(ledger["artifact_json"]["run_summary_path"])
    assert summary_path.exists()
    assert _read_json(summary_path) == ledger["summary_json"]
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
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
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
    assert ledger["summary_json"]["run_id"] == "sess-ledger-failed"
    assert ledger["summary_json"]["status"] == "failed"
    assert "forced failure for ledger" in str(ledger["summary_json"]["failure_reason"] or "")
    assert ledger["summary_json"]["duration_ms"] >= 0
    assert ledger["summary_json"]["control_plane"]["run_id"] == ledger["artifact_json"]["control_plane_run_record"]["run_id"]
    assert ledger["summary_json"]["control_plane"]["run_state"] == "failed_terminal"
    assert ledger["summary_json"]["control_plane"]["attempt_id"] == ledger["artifact_json"]["control_plane_attempt_record"]["attempt_id"]
    assert ledger["summary_json"]["control_plane"]["attempt_state"] == "attempt_failed"
    assert ledger["summary_json"]["control_plane"]["failure_class"] == "forced failure for ledger"
    assert ledger["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert ledger["artifact_json"]["gitea_export"]["commit"] == "def456"
    assert _read_json(Path(ledger["artifact_json"]["run_summary_path"])) == ledger["summary_json"]

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
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
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
    assert ledger["summary_json"]["status"] == "terminal_failure"
    assert ledger["summary_json"]["failure_reason"] is None
    assert ledger["summary_json"]["duration_ms"] >= 0
    assert ledger["summary_json"]["control_plane"]["run_id"] == ledger["artifact_json"]["control_plane_run_record"]["run_id"]
    assert ledger["summary_json"]["control_plane"]["run_state"] == "failed_terminal"
    assert ledger["summary_json"]["control_plane"]["attempt_id"] == ledger["artifact_json"]["control_plane_attempt_record"]["attempt_id"]
    assert ledger["summary_json"]["control_plane"]["attempt_state"] == "attempt_failed"
    assert _read_json(Path(ledger["artifact_json"]["run_summary_path"])) == ledger["summary_json"]


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_harvests_local_prompt_fallback_telemetry(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_prompt_fallback")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _execute_with_fallback_telemetry(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_json(
            workspace / "observability" / run_id / "ISSUE-1" / "001_lead_architect" / "model_response_raw.json",
            {
                "provider_backend": "ollama",
                "model": "packet1-fallback-proof:7b",
                "profile_id": "ollama.qwen.chatml.v1",
                "profile_resolution_path": "fallback",
                "retries": 0,
            },
        )
        _write_json(
            workspace / "agent_output" / "verification" / "runtime_verification.json",
            {"ok": True, "command_results": []},
        )
        return None

    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID", "ollama.qwen.chatml.v1")
    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_with_fallback_telemetry)

    await pipeline.run_epic(
        "ledger_epic_prompt_fallback",
        build_id="build-ledger-epic-prompt-fallback",
        session_id="sess-ledger-prompt-fallback",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-prompt-fallback")
    assert ledger is not None
    packet1 = ledger["summary_json"]["truthful_runtime_packet1"]
    assert packet1["provenance"]["actual_model"] == "packet1-fallback-proof:7b"
    assert packet1["provenance"]["actual_profile"] == "ollama.qwen.chatml.v1"
    assert packet1["provenance"]["fallback_occurred"] is True
    assert packet1["provenance"]["execution_profile"] == "fallback"
    assert packet1["classification"]["truth_classification"] == "degraded"
    assert packet1["defects"]["defect_families"] == ["silent_degraded_success"]
    assert packet1["packet1_conformance"]["status"] == "non_conformant"


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_marks_corrective_reprompt_runs_as_repaired(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_repaired")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _execute_with_repair_event(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_json(
            workspace / "agent_output" / "verification" / "runtime_verification.json",
            {"ok": True, "command_results": []},
        )
        log_event(
            "turn_corrective_reprompt",
            {
                "session_id": run_id,
                "issue_id": "ISSUE-1",
                "turn_index": 1,
                "contract_reasons": ["consistency_scope_contract_not_met"],
            },
            workspace=workspace,
        )
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_with_repair_event)

    await pipeline.run_epic(
        "ledger_epic_repaired",
        build_id="build-ledger-epic-repaired",
        session_id="sess-ledger-repaired",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-repaired")
    assert ledger is not None
    packet1 = ledger["summary_json"]["truthful_runtime_packet1"]
    packet2 = ledger["summary_json"]["truthful_runtime_packet2"]
    assert packet1["provenance"]["repair_occurred"] is True
    assert packet1["provenance"]["intended_model"] != PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["intended_profile"] != PACKET1_MISSING_TOKEN
    assert packet1["classification"]["truth_classification"] == "repaired"
    assert packet1["defects"]["defect_families"] == ["silent_repaired_success"]
    assert packet1["packet1_conformance"]["status"] == "non_conformant"
    assert packet2["repair_ledger"]["repair_occurred"] is True
    assert packet2["repair_ledger"]["repair_count"] == 1
    assert packet2["repair_ledger"]["final_disposition"] == "accepted_with_repair"
    assert packet2["repair_ledger"]["entries"] == [
        {
            "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
            "issue_id": "ISSUE-1",
            "turn_index": 1,
            "source_event": "turn_corrective_reprompt",
            "strategy": "corrective_reprompt",
            "reasons": ["consistency_scope_contract_not_met"],
            "material_change": True,
        }
    ]


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_records_artifact_provenance_for_generated_files(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_artifact_provenance")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_with_artifacts(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_protocol_write_receipts(
            workspace,
            session_id=run_id,
            rows=[
                ("REQ-1", "requirements_analyst", 1, "agent_output/requirements.txt", "op-req"),
                ("ARC-1", "architect", 1, "agent_output/design.txt", "op-arc"),
                ("COD-1", "coder", 1, "agent_output/main.py", "op-cod"),
            ],
        )
        _write_json(
            workspace / "agent_output" / "verification" / "runtime_verification.json",
            {"ok": True, "command_results": []},
        )
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_with_artifacts)

    await pipeline.run_epic(
        "ledger_epic_artifact_provenance",
        build_id="build-ledger-epic-artifact-provenance",
        session_id="sess-ledger-artifact-provenance",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-artifact-provenance")
    assert ledger is not None
    packet1 = ledger["summary_json"]["truthful_runtime_packet1"]
    artifact_provenance = ledger["summary_json"]["truthful_runtime_artifact_provenance"]
    entries = artifact_provenance["artifacts"]
    assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"
    assert [entry["artifact_path"] for entry in entries] == [
        "agent_output/design.txt",
        "agent_output/main.py",
        "agent_output/requirements.txt",
    ]
    requirements_entry = next(entry for entry in entries if entry["artifact_path"] == "agent_output/requirements.txt")
    assert requirements_entry["artifact_type"] == "requirements_document"
    assert requirements_entry["generator"] == "tool.write_file"
    assert requirements_entry["truth_classification"] == "direct"
    assert requirements_entry["issue_id"] == "REQ-1"
    assert requirements_entry["role_name"] == "requirements_analyst"
    assert requirements_entry["turn_index"] == 1
    protocol_events = await pipeline.run_ledger.list_events("sess-ledger-artifact-provenance")
    artifact_fact = next(row for row in protocol_events if row["kind"] == "artifact_provenance_fact")
    assert normalize_artifact_provenance_facts(artifact_fact["artifact_provenance_facts"]) == {
        "artifacts": entries
    }
    finalized = next(row for row in reversed(protocol_events) if row["kind"] == "run_finalized")
    assert finalized["summary"]["truthful_runtime_artifact_provenance"] == artifact_provenance


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_falls_back_to_tool_event_provenance_when_receipts_are_absent(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_artifact_provenance_log_fallback")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_with_logged_artifacts(**kwargs):
        run_id = str(kwargs["run_id"])
        _log_successful_write_file(
            workspace,
            session_id=run_id,
            issue_id="REQ-1",
            role_name="requirements_analyst",
            turn_index=1,
            artifact_path="agent_output/requirements.txt",
            operation_id="op-req-log",
        )
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_with_logged_artifacts)

    await pipeline.run_epic(
        "ledger_epic_artifact_provenance_log_fallback",
        build_id="build-ledger-epic-artifact-provenance-log-fallback",
        session_id="sess-ledger-artifact-provenance-log-fallback",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-artifact-provenance-log-fallback")
    assert ledger is not None
    artifact_provenance = ledger["summary_json"]["truthful_runtime_artifact_provenance"]
    assert artifact_provenance["artifacts"] == [
        {
            "artifact_path": "agent_output/requirements.txt",
            "artifact_type": "requirements_document",
            "generator": "tool.write_file",
            "generator_version": "unversioned",
            "source_hash": artifact_provenance["artifacts"][0]["source_hash"],
            "produced_at": artifact_provenance["artifacts"][0]["produced_at"],
            "truth_classification": "direct",
            "step_id": "REQ-1:1",
            "operation_id": "op-req-log",
            "issue_id": "REQ-1",
            "role_name": "requirements_analyst",
            "turn_index": 1,
        }
    ]
    assert len(str(artifact_provenance["artifacts"][0]["source_hash"])) == 64


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_records_phase_c_packet2_surfaces_for_required_source_attribution(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(
        test_root,
        "ledger_epic_phase_c_verified",
        truthful_runtime={"source_attribution_mode": "required"},
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_phase_c_verified(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_protocol_write_receipts(
            workspace,
            session_id=run_id,
            rows=[("ISSUE-1", "lead_architect", 1, "agent_output/main.py", "op-main")],
        )
        _write_json(
            workspace / "agent_output" / "source_attribution_receipt.json",
            {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim": "The implementation is supported by workspace artifacts.",
                        "source_ids": ["design", "implementation", "requirements"],
                    }
                ],
                "sources": [
                    {
                        "source_id": "design",
                        "title": "Design",
                        "uri": "agent_output/design.txt",
                        "kind": "workspace_artifact",
                    },
                    {
                        "source_id": "implementation",
                        "title": "Implementation",
                        "uri": "agent_output/main.py",
                        "kind": "workspace_artifact",
                    },
                    {
                        "source_id": "requirements",
                        "title": "Requirements",
                        "uri": "agent_output/requirements.txt",
                        "kind": "workspace_artifact",
                    },
                ],
            },
        )
        _write_protocol_receipt(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="write_file",
            tool_args={
                "path": "agent_output/source_attribution_receipt.json",
                "content": json.dumps(
                    {
                        "schema_version": "1.0",
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "claim": "The implementation is supported by workspace artifacts.",
                                "source_ids": ["design", "implementation", "requirements"],
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "design",
                                "title": "Design",
                                "uri": "agent_output/design.txt",
                                "kind": "workspace_artifact",
                            },
                            {
                                "source_id": "implementation",
                                "title": "Implementation",
                                "uri": "agent_output/main.py",
                                "kind": "workspace_artifact",
                            },
                            {
                                "source_id": "requirements",
                                "title": "Requirements",
                                "uri": "agent_output/requirements.txt",
                                "kind": "workspace_artifact",
                            },
                        ],
                    }
                ),
            },
            execution_result={"ok": True, "path": str(workspace / "agent_output" / "source_attribution_receipt.json")},
            operation_id="op-source-receipt",
            materialize_artifact=False,
        )
        _write_protocol_receipt(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="update_issue_status",
            tool_args={"issue_id": "ISSUE-1", "status": "done"},
            execution_result={"ok": True, "issue_id": "ISSUE-1", "status": "done"},
            operation_id="op-status-done",
            materialize_artifact=False,
        )
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.DONE)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_phase_c_verified)

    await pipeline.run_epic(
        "ledger_epic_phase_c_verified",
        build_id="build-ledger-epic-phase-c-verified",
        session_id="sess-ledger-phase-c-verified",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-phase-c-verified")
    assert ledger is not None
    assert ledger["status"] == "done"
    assert ledger["failure_reason"] is None
    packet1 = ledger["summary_json"]["truthful_runtime_packet1"]
    packet2 = ledger["summary_json"]["truthful_runtime_packet2"]
    assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"
    assert packet2["source_attribution"]["synthesis_status"] == "verified"
    assert packet2["source_attribution"]["claim_count"] == 1
    assert packet2["source_attribution"]["source_count"] == 3
    assert packet2["narration_to_effect_audit"]["missing_effect_count"] == 0
    surfaces = {row["surface"] for row in packet2["idempotency"]["surfaces"]}
    assert "artifact_write" in surfaces
    assert "status_update" in surfaces
    assert "source_attribution_receipt" in surfaces


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_records_phase_c_packet2_surfaces_from_legacy_turn_artifacts(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(
        test_root,
        "ledger_epic_phase_c_legacy_verified",
        truthful_runtime={"source_attribution_mode": "required"},
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_phase_c_legacy_verified(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_legacy_turn_artifact(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="write_file",
            tool_args={"path": "agent_output/main.py", "content": "print('ok')\n"},
            execution_result={"ok": True, "path": str(workspace / "agent_output" / "main.py")},
        )
        (workspace / "agent_output" / "requirements.txt").write_text("requirements\n", encoding="utf-8")
        (workspace / "agent_output" / "design.txt").write_text("design\n", encoding="utf-8")
        _write_legacy_turn_artifact(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="write_file",
            tool_args={
                "path": "agent_output/source_attribution_receipt.json",
                "content": json.dumps(
                    {
                        "schema_version": "1.0",
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "claim": "The implementation is supported by workspace artifacts.",
                                "source_ids": ["design", "implementation", "requirements"],
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "design",
                                "title": "Design",
                                "uri": "agent_output/design.txt",
                                "kind": "workspace_artifact",
                            },
                            {
                                "source_id": "implementation",
                                "title": "Implementation",
                                "uri": "agent_output/main.py",
                                "kind": "workspace_artifact",
                            },
                            {
                                "source_id": "requirements",
                                "title": "Requirements",
                                "uri": "agent_output/requirements.txt",
                                "kind": "workspace_artifact",
                            },
                        ],
                    }
                ),
            },
            execution_result={"ok": True, "path": str(workspace / "agent_output" / "source_attribution_receipt.json")},
        )
        _write_legacy_turn_artifact(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="update_issue_status",
            tool_args={"status": "done"},
            execution_result={"ok": True, "issue_id": "ISSUE-1", "status": "done"},
            materialize_artifact=False,
        )
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.DONE)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_phase_c_legacy_verified)

    await pipeline.run_epic(
        "ledger_epic_phase_c_legacy_verified",
        build_id="build-ledger-epic-phase-c-legacy-verified",
        session_id="sess-ledger-phase-c-legacy-verified",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-phase-c-legacy-verified")
    assert ledger is not None
    assert ledger["status"] == "done"
    packet2 = ledger["summary_json"]["truthful_runtime_packet2"]
    assert packet2["source_attribution"]["synthesis_status"] == "verified"
    assert packet2["narration_to_effect_audit"]["missing_effect_count"] == 0
    surfaces = {row["surface"] for row in packet2["idempotency"]["surfaces"]}
    assert "artifact_write" in surfaces
    assert "status_update" in surfaces
    assert "source_attribution_receipt" in surfaces


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_blocks_done_run_when_required_source_attribution_is_missing(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(
        test_root,
        "ledger_epic_phase_c_blocked",
        truthful_runtime={"source_attribution_mode": "required"},
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_phase_c_blocked(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_protocol_write_receipts(
            workspace,
            session_id=run_id,
            rows=[("ISSUE-1", "lead_architect", 1, "agent_output/main.py", "op-main")],
        )
        _write_protocol_receipt(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="update_issue_status",
            tool_args={"issue_id": "ISSUE-1", "status": "done"},
            execution_result={"ok": True, "issue_id": "ISSUE-1", "status": "done"},
            operation_id="op-status-done",
            materialize_artifact=False,
        )
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.DONE)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_phase_c_blocked)

    await pipeline.run_epic(
        "ledger_epic_phase_c_blocked",
        build_id="build-ledger-epic-phase-c-blocked",
        session_id="sess-ledger-phase-c-blocked",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-phase-c-blocked")
    assert ledger is not None
    assert ledger["status"] == "terminal_failure"
    assert ledger["failure_reason"] == "source_attribution_receipt_missing"
    packet2 = ledger["summary_json"]["truthful_runtime_packet2"]
    assert packet2["source_attribution"]["synthesis_status"] == "blocked"
    assert packet2["source_attribution"]["missing_requirements"] == ["source_attribution_receipt_missing"]


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_narration_effect_audit_detects_missing_written_source_receipt(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(
        test_root,
        "ledger_epic_phase_c_missing_effect",
        truthful_runtime={"source_attribution_mode": "optional"},
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
    )

    async def _execute_phase_c_missing_effect(**kwargs):
        run_id = str(kwargs["run_id"])
        _write_protocol_write_receipts(
            workspace,
            session_id=run_id,
            rows=[("ISSUE-1", "lead_architect", 1, "agent_output/main.py", "op-main")],
        )
        _write_protocol_receipt(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="write_file",
            tool_args={
                "path": "agent_output/source_attribution_receipt.json",
                "content": '{"schema_version":"1.0"}',
            },
            execution_result={"ok": True, "path": str(workspace / "agent_output" / "source_attribution_receipt.json")},
            operation_id="op-source-receipt",
            materialize_artifact=False,
        )
        _write_protocol_receipt(
            workspace,
            session_id=run_id,
            issue_id="ISSUE-1",
            role_name="lead_architect",
            turn_index=1,
            tool="update_issue_status",
            tool_args={"issue_id": "ISSUE-1", "status": "done"},
            execution_result={"ok": True, "issue_id": "ISSUE-1", "status": "done"},
            operation_id="op-status-done",
            materialize_artifact=False,
        )
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.DONE)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _execute_phase_c_missing_effect)

    await pipeline.run_epic(
        "ledger_epic_phase_c_missing_effect",
        build_id="build-ledger-epic-phase-c-missing-effect",
        session_id="sess-ledger-phase-c-missing-effect",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-phase-c-missing-effect")
    assert ledger is not None
    assert ledger["status"] == "done"
    packet2 = ledger["summary_json"]["truthful_runtime_packet2"]
    audit_entries = packet2["narration_to_effect_audit"]["entries"]
    missing_entry = next(
        row for row in audit_entries if row["effect_target"] == "agent_output/source_attribution_receipt.json"
    )
    assert missing_entry["audit_status"] == "missing"
    assert missing_entry["failure_reason"] == "workspace_artifact_missing"
    assert packet2["source_attribution"]["synthesis_status"] == "optional_unverified"


# Layer: integration
@pytest.mark.asyncio
async def test_run_ledger_emits_degraded_run_summary_when_canonical_generation_fails(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "ledger_epic_summary_fallback")

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

    async def _raise_summary_generation(**_kwargs):
        raise ValueError("forced summary generation failure")

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _no_export_run)
    monkeypatch.setattr(
        execution_pipeline_module,
        "generate_run_summary_for_finalize",
        _raise_summary_generation,
    )

    await pipeline.run_epic(
        "ledger_epic_summary_fallback",
        build_id="build-ledger-epic-summary-fallback",
        session_id="sess-ledger-summary-fallback",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-summary-fallback")
    assert ledger is not None
    assert ledger["summary_json"]["status"] == "incomplete"
    assert ledger["summary_json"]["duration_ms"] is None
    assert ledger["artifact_json"]["run_summary_generation_error"]["error_type"] == "ValueError"
    runtime_events_path = workspace / "agent_output" / "observability" / "runtime_events.jsonl"
    for _ in range(20):
        if runtime_events_path.exists():
            break
        await asyncio.sleep(0.01)
    assert runtime_events_path.exists()
    runtime_events = [json.loads(line) for line in runtime_events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    packet1_failure = next(event for event in runtime_events if event["event"] == "packet1_emission_failure")
    assert packet1_failure["packet1_conformance"]["status"] == "non_conformant"
    assert packet1_failure["packet1_conformance"]["reasons"] == ["packet1_emission_failure"]
    summary_path = Path(ledger["artifact_json"]["run_summary_path"])
    assert summary_path.exists()
    assert _read_json(summary_path) == ledger["summary_json"]


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
    assert artifact_json["run_identity"]["identity_scope"] == "session_bootstrap"
    assert artifact_json["run_identity"]["projection_only"] is True
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
    assert artifact_json["retry_classification_policy"]["schema_version"] == "1.0"
    assert artifact_json["retry_classification_policy"]["attempt_history_authoritative"] is False
    retry_signals = [row["signal"] for row in artifact_json["retry_classification_policy"]["rows"]]
    assert "model_timeout_retry" in retry_signals
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
