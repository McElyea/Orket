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


# Layer: contract
def test_run_summary_schema_contract_is_canonical() -> None:
    payload = build_run_summary_payload(
        run_id="sess-summary-contract",
        status="incomplete",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={"run_identity": {"run_id": "sess-summary-contract"}},
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
    assert payload["duration_ms"] == 5000


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
            "run_identity": {"run_id": "sess-summary-generate", "start_time": _STARTED_AT},
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
    run_identity = {
        "run_id": session_id,
        "workload": "run-summary-test",
        "start_time": _STARTED_AT,
    }
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
