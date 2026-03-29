from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.workflows.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from orket.runtime.run_summary import (
    build_run_summary_payload,
    generate_run_summary_for_finalize,
    reconstruct_run_summary,
    validate_run_summary_payload,
    write_run_summary_artifact,
)

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"


def _run_identity(*, run_id: str, workload: str = "run-summary-test") -> dict[str, str | bool]:
    return {
        "run_id": run_id,
        "workload": workload,
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
        "projection_only": True,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


def _tool_call_payload(
    *,
    session_id: str,
    operation_id: str,
    tool_name: str,
    replayed: bool,
) -> dict[str, Any]:
    tool_args = {"path": "README.md"}
    manifest = build_tool_invocation_manifest(run_id=session_id, tool_name=tool_name)
    return {
        "operation_id": operation_id,
        "step_id": "ISSUE-1:1",
        "tool": tool_name,
        "tool_args": tool_args,
        "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_contract_version=str(manifest.get("tool_contract_version") or ""),
            capability_profile=str(manifest.get("capability_profile") or ""),
        ),
        "replayed": bool(replayed),
    }


def _tool_result_payload(
    *,
    call_payload: dict[str, Any],
    call_sequence_number: int,
    replayed: bool,
) -> dict[str, Any]:
    return {
        "operation_id": str(call_payload.get("operation_id") or ""),
        "step_id": str(call_payload.get("step_id") or ""),
        "tool": str(call_payload.get("tool") or ""),
        "result": {"ok": True, "content": "ok"},
        "call_sequence_number": int(call_sequence_number),
        "tool_invocation_manifest": dict(call_payload.get("tool_invocation_manifest") or {}),
        "tool_call_hash": str(call_payload.get("tool_call_hash") or ""),
        "replayed": bool(replayed),
    }


def _control_plane_summary_artifacts(*, session_id: str) -> dict[str, Any]:
    run_id = f"cards-epic-run:{session_id}:build-1:20360305T120000000000Z"
    attempt_id = f"{run_id}:attempt:0001"
    return {
        "run_identity": _run_identity(run_id=session_id, workload="cards-epic"),
        "control_plane_run_record": {
            "contract_version": "control_plane.contract.v1",
            "run_id": run_id,
            "workload_id": "cards-epic",
            "workload_version": "1.0",
            "policy_snapshot_id": "policy-1",
            "policy_digest": "sha256:policy-1",
            "configuration_snapshot_id": "config-1",
            "configuration_digest": "sha256:config-1",
            "creation_timestamp": _STARTED_AT,
            "admission_decision_receipt_ref": "admission-1",
            "lifecycle_state": "waiting_on_observation",
            "current_attempt_id": attempt_id,
        },
        "control_plane_attempt_record": {
            "contract_version": "control_plane.contract.v1",
            "attempt_id": attempt_id,
            "run_id": run_id,
            "attempt_ordinal": 1,
            "attempt_state": "attempt_waiting",
            "starting_state_snapshot_ref": "admission-1",
            "start_timestamp": _STARTED_AT,
        },
        "control_plane_step_record": {
            "contract_version": "control_plane.contract.v1",
            "step_id": f"{run_id}:step:start",
            "attempt_id": attempt_id,
            "step_kind": "cards_epic_session_start",
            "input_ref": "admission-1",
            "output_ref": "admission-1",
            "capability_used": "deterministic_compute",
            "resources_touched": ["epic:summary", "build:build-1"],
            "observed_result_classification": "cards_epic_run_started",
            "receipt_refs": ["admission-1"],
            "closure_classification": "step_completed",
        },
    }


# Layer: contract
def test_run_summary_schema_contract_is_canonical() -> None:
    payload = build_run_summary_payload(
        run_id="sess-summary-contract",
        status="incomplete",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={"run_identity": _run_identity(run_id="sess-summary-contract")},
    )

    validate_run_summary_payload(payload)
    schema = _read_json(Path("core/artifacts/run_summary_schema.json"))
    assert schema["required"] == [
        "run_id",
        "status",
        "duration_ms",
        "tools_used",
        "artifact_ids",
        "failure_reason",
    ]
    assert "truthful_runtime_artifact_provenance" in schema["properties"]
    assert "control_plane" in schema["properties"]
    assert payload["duration_ms"] == 5000


# Layer: contract
def test_run_summary_emits_control_plane_projection() -> None:
    payload = build_run_summary_payload(
        run_id="sess-summary-control-plane",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts=_control_plane_summary_artifacts(session_id="sess-summary-control-plane"),
    )

    assert payload["control_plane"] == {
        "projection_source": "control_plane_records",
        "projection_only": True,
        "run_id": "cards-epic-run:sess-summary-control-plane:build-1:20360305T120000000000Z",
        "run_state": "waiting_on_observation",
        "workload_id": "cards-epic",
        "workload_version": "1.0",
        "policy_snapshot_id": "policy-1",
        "configuration_snapshot_id": "config-1",
        "current_attempt_id": "cards-epic-run:sess-summary-control-plane:build-1:20360305T120000000000Z:attempt:0001",
        "attempt_id": "cards-epic-run:sess-summary-control-plane:build-1:20360305T120000000000Z:attempt:0001",
        "attempt_state": "attempt_waiting",
        "attempt_ordinal": 1,
        "step_id": "cards-epic-run:sess-summary-control-plane:build-1:20360305T120000000000Z:step:start",
        "step_kind": "cards_epic_session_start",
        "step_capability_used": "deterministic_compute",
        "step_resources_touched": ["epic:summary", "build:build-1"],
        "step_receipt_refs": ["admission-1"],
    }


# Layer: integration
def test_control_plane_reconstruction_matches_emitted_summary() -> None:
    artifacts = _control_plane_summary_artifacts(session_id="sess-summary-control-plane-reconstruct")
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-summary-control-plane-reconstruct",
            "timestamp": _STARTED_AT,
            "artifacts": artifacts,
        },
        {
            "kind": "tool_call",
            "event_seq": 2,
            "tool_name": "workspace.read",
        },
        {
            "kind": "run_finalized",
            "event_seq": 3,
            "run_id": "sess-summary-control-plane-reconstruct",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]

    reconstructed = reconstruct_run_summary(events, session_id="sess-summary-control-plane-reconstruct")
    emitted = build_run_summary_payload(
        run_id="sess-summary-control-plane-reconstruct",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts=artifacts,
    )

    assert reconstructed == emitted


# Layer: integration
def test_reconstruct_run_summary_rejects_run_identity_run_id_mismatch() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-summary-reconstruct-mismatch",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": _run_identity(run_id="sess-summary-other"),
            },
        },
        {
            "kind": "run_finalized",
            "event_seq": 2,
            "run_id": "sess-summary-reconstruct-mismatch",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]

    with pytest.raises(ValueError, match="run_summary_run_identity_run_id_mismatch"):
        reconstruct_run_summary(events, session_id="sess-summary-reconstruct-mismatch")


# Layer: contract
def test_run_summary_emits_odr_cards_runtime_fields() -> None:
    payload = build_run_summary_payload(
        run_id="sess-summary-odr",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-summary-odr", workload="cards-runtime"),
            "cards_runtime_facts": {
                "execution_profile": "odr_prebuild_builder_guard_v1",
                "stop_reason": "completed",
                "odr_active": True,
                "odr_valid": True,
                "odr_pending_decisions": 0,
                "odr_stop_reason": "STABLE_DIFF_FLOOR",
                "odr_artifact_path": "observability/sess-summary-odr/ISSUE-1/odr_refinement.json",
            },
        },
    )

    assert payload["execution_profile"] == "odr_prebuild_builder_guard_v1"
    assert payload["odr_active"] is True
    assert payload["odr_valid"] is True
    assert payload["odr_pending_decisions"] == 0
    assert payload["odr_stop_reason"] == "STABLE_DIFF_FLOOR"
    assert payload["odr_artifact_path"] == "observability/sess-summary-odr/ISSUE-1/odr_refinement.json"


# Layer: contract
@pytest.mark.asyncio
async def test_generate_run_summary_for_finalize_uses_receipts_and_filtered_artifact_ids(tmp_path: Path) -> None:
    receipt_path = (
        tmp_path
        / "observability"
        / "sess-summary-generate"
        / "ISSUE-1"
        / "001_coder"
        / "protocol_receipts.log"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_lines = [
        json.dumps({"tool": "workspace.read"}, separators=(",", ":")),
        json.dumps({"tool_name": "workspace.read"}, separators=(",", ":")),
        json.dumps({"tool": "workspace.search"}, separators=(",", ":")),
    ]
    receipt_path.write_bytes(("\n".join(receipt_lines) + "\n").encode("utf-8"))

    payload = await generate_run_summary_for_finalize(
        workspace=tmp_path,
        run_id="sess-summary-generate",
        status="incomplete",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        artifacts={
            "run_identity": _run_identity(run_id="sess-summary-generate"),
            "route_decision_artifact": {"route_target": "epic"},
            "tool_registry_snapshot": {"tool_registry_version": "1.2.0"},
            "run_summary": {"ignored": True},
            "run_summary_path": "runs/sess-summary-generate/run_summary.json",
            "gitea_export": {"provider": "gitea"},
            "workspace": str(tmp_path),
        },
    )

    assert payload["tools_used"] == ["workspace.read", "workspace.search"]
    assert payload["artifact_ids"] == [
        "route_decision_artifact",
        "run_identity",
        "tool_registry_snapshot",
    ]


async def _record_protocol_run(
    *,
    root: Path,
    session_id: str,
    replayed: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = AsyncProtocolRunLedgerRepository(root)
    run_identity = _run_identity(run_id=session_id)
    await repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Run Summary Test",
        department="core",
        build_id="build-run-summary",
        artifacts={"run_identity": run_identity},
    )
    call_payload = _tool_call_payload(
        session_id=session_id,
        operation_id="op-1",
        tool_name="workspace.read",
        replayed=replayed,
    )
    call_event = await repo.append_event(
        session_id=session_id,
        kind="tool_call",
        payload=call_payload,
    )
    await repo.append_event(
        session_id=session_id,
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call_event["event_seq"]),
            replayed=replayed,
        ),
    )
    summary_artifacts = {"run_identity": run_identity}
    summary = build_run_summary_payload(
        run_id=session_id,
        status="incomplete",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts=summary_artifacts,
    )
    summary_path = await write_run_summary_artifact(
        root=root,
        session_id=session_id,
        payload=summary,
    )
    summary_artifacts["run_summary"] = dict(summary)
    summary_artifacts["run_summary_path"] = str(summary_path)
    await repo.finalize_run(
        session_id=session_id,
        status="incomplete",
        summary=summary,
        artifacts=summary_artifacts,
        finalized_at=_FINALIZED_AT,
    )
    emitted = _read_json(summary_path)
    reconstructed = reconstruct_run_summary(await repo.list_events(session_id), session_id=session_id)
    return emitted, reconstructed


# Layer: integration
@pytest.mark.asyncio
async def test_run_summary_emitted_and_reconstructed_live_replay_are_equal(tmp_path: Path) -> None:
    live_emitted, live_reconstructed = await _record_protocol_run(
        root=tmp_path / "live",
        session_id="sess-run-summary-parity",
        replayed=False,
    )
    replay_emitted, replay_reconstructed = await _record_protocol_run(
        root=tmp_path / "replay",
        session_id="sess-run-summary-parity",
        replayed=True,
    )

    assert live_emitted == live_reconstructed
    assert replay_emitted == replay_reconstructed
    assert live_emitted == replay_emitted
