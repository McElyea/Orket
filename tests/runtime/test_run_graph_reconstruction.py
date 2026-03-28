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
from orket.runtime.run_graph_reconstruction import (
    reconstruct_run_graph,
    reconstruct_run_graph_from_events_log,
)


def _sample_events() -> list[dict[str, Any]]:
    compat_translation = {
        "compat_tool_name": "openclaw.file_edit",
        "mapping_version": 1,
        "mapping_determinism": "workspace",
        "schema_compatibility_range": ">=1.0.0 <2.0.0",
        "mapped_core_tools": ["workspace.search", "file.patch"],
        "translation_hash": "a" * 64,
    }
    manifest = build_tool_invocation_manifest(
        run_id="sess-graph",
        tool_name="openclaw.file_edit",
        control_plane_run_id="turn-tool-run:sess-graph:ISSUE-1:architect:0001",
        control_plane_attempt_id="turn-tool-run:sess-graph:ISSUE-1:architect:0001:attempt:0001",
        control_plane_step_id="op-1",
        control_plane_reservation_id="turn-tool-reservation:turn-tool-run:sess-graph:ISSUE-1:architect:0001",
        control_plane_lease_id="turn-tool-lease:turn-tool-run:sess-graph:ISSUE-1:architect:0001",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    return [
        {
            "event_seq": 1,
            "sequence_number": 1,
            "ledger_schema_version": "1.0",
            "kind": "run_started",
            "run_id": "sess-graph",
            "run_name": "Graph Run",
            "artifacts": {"run_identity": {"run_id": "sess-graph", "workload": "Graph Run"}},
        },
        {
            "event_seq": 2,
            "sequence_number": 2,
            "ledger_schema_version": "1.0",
            "kind": "tool_call",
            "run_id": "sess-graph",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "tool_name": "openclaw.file_edit",
            "tool_call_hash": "b" * 64,
            "tool_invocation_manifest": manifest,
        },
        {
            "event_seq": 3,
            "sequence_number": 3,
            "ledger_schema_version": "1.0",
            "kind": "operation_result",
            "run_id": "sess-graph",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "call_sequence_number": 2,
            "result": {
                "ok": True,
                "compat_translation": compat_translation,
            },
            "tool_invocation_manifest": manifest,
            "tool_call_hash": "b" * 64,
        },
        {
            "event_seq": 4,
            "sequence_number": 4,
            "ledger_schema_version": "1.0",
            "kind": "run_finalized",
            "run_id": "sess-graph",
            "status": "incomplete",
            "artifacts": {"run_summary": {"session_status": "incomplete"}},
        },
    ]


def _tool_call_payload(
    *,
    session_id: str,
    operation_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
    replayed: bool = False,
) -> dict[str, Any]:
    manifest = build_tool_invocation_manifest(
        run_id=session_id,
        tool_name=tool_name,
        control_plane_run_id=f"turn-tool-run:{session_id}:ISSUE-1:architect:0001",
        control_plane_attempt_id=f"turn-tool-run:{session_id}:ISSUE-1:architect:0001:attempt:0001",
        control_plane_step_id=operation_id,
        control_plane_reservation_id=f"turn-tool-reservation:turn-tool-run:{session_id}:ISSUE-1:architect:0001",
        control_plane_lease_id=f"turn-tool-lease:turn-tool-run:{session_id}:ISSUE-1:architect:0001",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    return {
        "operation_id": operation_id,
        "step_id": "ISSUE-1:1",
        "tool": tool_name,
        "tool_args": dict(tool_args),
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
    result: dict[str, Any],
    replayed: bool = False,
) -> dict[str, Any]:
    return {
        "operation_id": str(call_payload.get("operation_id") or ""),
        "step_id": str(call_payload.get("step_id") or ""),
        "tool": str(call_payload.get("tool") or ""),
        "result": dict(result or {}),
        "call_sequence_number": int(call_sequence_number),
        "tool_invocation_manifest": dict(call_payload.get("tool_invocation_manifest") or {}),
        "tool_call_hash": str(call_payload.get("tool_call_hash") or ""),
        "replayed": bool(replayed),
    }


# Layer: contract
def test_run_graph_reconstruction_is_reproducible_and_idempotent() -> None:
    events = _sample_events()
    graph_a = reconstruct_run_graph(events, session_id="sess-graph")
    graph_b = reconstruct_run_graph(list(reversed(events)), session_id="sess-graph")

    assert graph_a == graph_b
    assert graph_a["run_graph_schema_version"] == "1.0"
    assert graph_a["node_count"] == len(graph_a["nodes"])
    assert graph_a["edge_count"] == len(graph_a["edges"])
    assert len(str(graph_a["graph_digest"])) == 64


# Layer: contract
def test_run_graph_reconstruction_enforces_artifact_lineage() -> None:
    graph = reconstruct_run_graph(_sample_events(), session_id="sess-graph")
    artifact_nodes = {
        str(node.get("id") or "")
        for node in graph["nodes"]
        if str(node.get("type") or "") == "artifact"
    }
    produced_targets = {
        str(edge.get("target") or "")
        for edge in graph["edges"]
        if str(edge.get("type") or "") == "artifact_produced"
    }
    assert artifact_nodes
    assert artifact_nodes.issubset(produced_targets)


# Layer: contract
def test_run_graph_reconstruction_builds_compatibility_expansion_edges() -> None:
    graph = reconstruct_run_graph(_sample_events(), session_id="sess-graph")
    compat_nodes = [node for node in graph["nodes"] if node.get("type") == "compat_mapping"]
    assert len(compat_nodes) == 1
    compat_node_id = str(compat_nodes[0]["id"])
    assert compat_nodes[0]["mapping_version"] == 1
    assert compat_nodes[0]["mapped_core_tools"] == ["workspace.search", "file.patch"]

    compat_edge = next(
        edge for edge in graph["edges"] if edge.get("type") == "compat_expansion"
    )
    assert compat_edge["source"] == "tool_call:2"
    assert compat_edge["target"] == compat_node_id
    compat_artifact_edge = next(
        edge
        for edge in graph["edges"]
        if edge.get("type") == "artifact_produced" and edge.get("source") == compat_node_id
    )
    assert str(compat_artifact_edge["target"]).startswith("artifact:compat_translation:")


# Layer: contract
def test_run_graph_reconstruction_preserves_canonical_control_plane_refs_on_tool_call_nodes() -> None:
    graph = reconstruct_run_graph(_sample_events(), session_id="sess-graph")

    call_node = next(node for node in graph["nodes"] if node.get("type") == "tool_call")

    assert call_node["step_id"] == "ISSUE-1:1"
    assert call_node["control_plane_run_id"] == "turn-tool-run:sess-graph:ISSUE-1:architect:0001"
    assert call_node["control_plane_attempt_id"] == "turn-tool-run:sess-graph:ISSUE-1:architect:0001:attempt:0001"
    assert call_node["control_plane_step_id"] == "op-1"
    assert (
        call_node["control_plane_reservation_id"]
        == "turn-tool-reservation:turn-tool-run:sess-graph:ISSUE-1:architect:0001"
    )
    assert call_node["control_plane_lease_id"] == "turn-tool-lease:turn-tool-run:sess-graph:ISSUE-1:architect:0001"
    assert call_node["control_plane_resource_id"] == "namespace:issue:ISSUE-1"


async def _record_protocol_run(
    *,
    root: Path,
    session_id: str,
    replayed: bool,
) -> dict[str, Any]:
    repo = AsyncProtocolRunLedgerRepository(root)
    await repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Run Graph Integration",
        department="core",
        build_id="build-run-graph",
    )
    call_payload = _tool_call_payload(
        session_id=session_id,
        operation_id="op-1",
        tool_name="workspace.read",
        tool_args={"path": "README.md"},
        replayed=replayed,
    )
    call_event = await repo.append_event(
        session_id=session_id,
        kind="tool_call",
        payload=call_payload,
    )
    assert call_event["kind"] == "tool_call"
    result_event = await repo.append_event(
        session_id=session_id,
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call_event["event_seq"]),
            result={"ok": True, "content": "ok"},
            replayed=replayed,
        ),
    )
    assert result_event["kind"] == "operation_result"
    await repo.finalize_run(
        session_id=session_id,
        status="incomplete",
        summary={"session_status": "incomplete"},
    )
    run_graph_path = root / "runs" / session_id / "run_graph.json"
    assert run_graph_path.exists()
    return json.loads(run_graph_path.read_text(encoding="utf-8"))


# Layer: integration
@pytest.mark.asyncio
async def test_protocol_run_graph_reconstruction_writes_golden_artifact(tmp_path: Path) -> None:
    session_id = "sess-run-graph-golden"
    graph = await _record_protocol_run(root=tmp_path, session_id=session_id, replayed=False)

    assert graph["run_graph_schema_version"] == "1.0"
    assert graph["run_id"] == session_id
    tool_call_node = next(node for node in graph["nodes"] if node.get("type") == "tool_call")
    assert tool_call_node["control_plane_run_id"] == "turn-tool-run:sess-run-graph-golden:ISSUE-1:architect:0001"
    assert tool_call_node["control_plane_attempt_id"] == (
        "turn-tool-run:sess-run-graph-golden:ISSUE-1:architect:0001:attempt:0001"
    )
    assert tool_call_node["control_plane_step_id"] == "op-1"
    assert tool_call_node["control_plane_resource_id"] == "namespace:issue:ISSUE-1"
    assert any(node.get("type") == "artifact" for node in graph["nodes"])
    assert any(edge.get("type") == "call_result" for edge in graph["edges"])

    rebuilt = reconstruct_run_graph_from_events_log(
        events_log_path=tmp_path / "runs" / session_id / "events.log",
        session_id=session_id,
    )
    assert rebuilt == graph


# Layer: integration
@pytest.mark.asyncio
async def test_run_graph_live_vs_replay_parity_for_deterministic_runs(tmp_path: Path) -> None:
    live = await _record_protocol_run(root=tmp_path / "live", session_id="sess-run-graph-parity", replayed=False)
    replay = await _record_protocol_run(root=tmp_path / "replay", session_id="sess-run-graph-parity", replayed=True)
    assert live == replay
