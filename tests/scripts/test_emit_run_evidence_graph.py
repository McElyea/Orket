# LIFECYCLE: live
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord
from scripts.observability.emit_run_evidence_graph import main
from tests.runtime.run_evidence_graph_test_support import (
    GENERATED_AT,
    seed_complete_primary_lineage_sqlite,
)


# Layer: integration
def test_emit_run_evidence_graph_writes_canonical_artifact_family(tmp_path: Path) -> None:
    _, _, db_path, session_id, run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    mermaid_path = tmp_path / "runs" / session_id / "run_evidence_graph.mmd"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["graph_result"] == "complete"
    assert payload["selected_views"] == [
        "full_lineage",
        "failure_path",
        "resource_authority_path",
        "closure_path",
    ]
    assert mermaid_path.exists()
    assert html_path.exists()
    assert 'subgraph view_full_lineage["Full Lineage | ' in mermaid_path.read_text(encoding="utf-8")
    assert "Failure Path" in html_path.read_text(encoding="utf-8")


# Layer: integration
def test_emit_run_evidence_graph_returns_blocked_when_selected_run_has_no_primary_lineage(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".orket" / "durable" / "db" / "control_plane_records.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = "sess-graph-blocked"
    run_id = f"kernel-action-run:{session_id}:trace-missing"
    (tmp_path / "runs" / session_id).mkdir(parents=True, exist_ok=True)

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--session-id",
            session_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 1
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["graph_result"] == "blocked"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert "run_record_missing" in html_path.read_text(encoding="utf-8")


# Layer: integration
def test_emit_run_evidence_graph_accepts_authority_and_decision_views(tmp_path: Path) -> None:
    _, _, db_path, session_id, run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
            "--view",
            "decision",
            "--view",
            "authority",
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["selected_views"] == ["authority", "decision"]
    html = html_path.read_text(encoding="utf-8")
    assert "Authority" in html
    assert "Decision" in html


# Layer: integration
def test_emit_run_evidence_graph_resolves_control_plane_run_id_from_session_summary(tmp_path: Path) -> None:
    _, _, db_path, session_id, control_plane_run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))
    run_summary_path = tmp_path / "runs" / session_id / "run_summary.json"
    payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
    payload["run_id"] = session_id
    payload["control_plane"] = {"run_id": control_plane_run_id}
    run_summary_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    exit_code = main(
        [
            "--run-id",
            session_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    graph_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert graph_payload["run_id"] == control_plane_run_id
    assert graph_payload["graph_result"] in {"complete", "degraded"}


# Layer: integration
def test_emit_run_evidence_graph_supports_outward_run_id_without_legacy_session(tmp_path: Path) -> None:
    db_path = tmp_path / "outward.sqlite3"
    run_id = "outward-graph-run"
    namespace = "outward_graph_namespace"
    asyncio.run(_seed_outward_graph_run(db_path=db_path, run_id=run_id, namespace=namespace))

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--workspace-root",
            str(tmp_path),
            "--outward-pipeline-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    assert not (tmp_path / "runs" / run_id).exists()
    graph_path = tmp_path / "workspace" / namespace / "runs" / run_id / "run_evidence_graph.json"
    svg_path = tmp_path / "workspace" / namespace / "runs" / run_id / "run_evidence_graph.svg"
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    assert payload["graph_kind"] == "outward_pipeline"
    assert payload["graph_result"] == "complete"
    assert payload["run_id"] == run_id
    assert payload["proposals"][0]["proposal_id"] == f"proposal:{run_id}:write_file:0001"
    assert payload["tool_invocations"][0]["payload"]["outcome"] == "success"
    assert payload["ledger_references"]["verification_result"] == "valid"
    assert payload["events"][0]["event_hash"]
    assert svg_path.exists()


async def _seed_outward_graph_run(*, db_path: Path, run_id: str, namespace: str) -> None:
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    approval_store = OutwardApprovalStore(db_path)
    await run_store.create(
        OutwardRunRecord(
            run_id=run_id,
            status="completed",
            namespace=namespace,
            submitted_at="2026-04-26T00:00:00+00:00",
            started_at="2026-04-26T00:00:01+00:00",
            completed_at="2026-04-26T00:00:06+00:00",
            current_turn=1,
            max_turns=20,
            task={"description": "outward graph", "instruction": "write", "model_governed_tool_call": {"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}},
            policy_overrides={"approval_required_tools": ["write_file"]},
        )
    )
    await approval_store.save(
        OutwardApprovalProposal(
            proposal_id=f"proposal:{run_id}:write_file:0001",
            run_id=run_id,
            namespace=namespace,
            tool="write_file",
            args_preview={"path": "out.txt", "content": "[REDACTED]"},
            context_summary="model-produced governed tool call from live provider response",
            risk_level="write",
            submitted_at="2026-04-26T00:00:03+00:00",
            expires_at="2026-04-26T00:10:03+00:00",
            status="approved",
            operator_ref="operator:test",
            decision="approve",
            decided_at="2026-04-26T00:00:04+00:00",
        )
    )
    for event in [
        ("run_submitted", 0, "operator", "2026-04-26T00:00:00+00:00", {"status": "queued"}),
        ("run_started", 0, "outward-agent", "2026-04-26T00:00:01+00:00", {"status": "running"}),
        ("proposal_made", 1, "outward-agent", "2026-04-26T00:00:02+00:00", {"tool": "write_file"}),
        ("proposal_pending_approval", 1, "operator", "2026-04-26T00:00:03+00:00", {"proposal_id": f"proposal:{run_id}:write_file:0001"}),
        ("proposal_approved", 1, "operator", "2026-04-26T00:00:04+00:00", {"proposal_id": f"proposal:{run_id}:write_file:0001"}),
        ("tool_invoked", 1, "outward-agent", "2026-04-26T00:00:05+00:00", {"connector_name": "write_file", "args_hash": "abc", "result_summary": {"ok": True}, "duration_ms": 0, "outcome": "success"}),
        ("commitment_recorded", 1, "outward-agent", "2026-04-26T00:00:06+00:00", {"outcome": "committed"}),
    ]:
        event_type, turn, agent_id, at, payload = event
        await event_store.append(
            LedgerEvent(
                event_id=f"run:{run_id}:{event_type}",
                event_type=event_type,
                run_id=run_id,
                turn=turn,
                agent_id=agent_id,
                at=at,
                payload={"run_id": run_id, **payload},
            )
        )
