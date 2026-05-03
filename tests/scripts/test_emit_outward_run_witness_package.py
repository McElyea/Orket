from __future__ import annotations

import hashlib
import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_run_execution_plan import args_hash
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord
from scripts.proof.emit_outward_run_witness_package import main
from scripts.proof.outward_run_witness_builder import build_outward_run_witness_package
from scripts.proof.verify_outward_run_witness_package import verify_package


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_package_producer_emits_layout_from_seeded_outward_database(tmp_path: Path) -> None:
    """Layer: contract. Verifies the producer emits the package layout from persisted outward records."""
    db_path = tmp_path / "outward.sqlite3"
    workspace_root = tmp_path
    await _seed_approved_run(db_path, workspace_root)
    output = tmp_path / "package"

    await build_outward_run_witness_package(
        db_path=db_path,
        workspace_root=workspace_root,
        run_id="run-producer",
        output_dir=output,
    )

    assert (output / "manifest.json").exists()
    assert (output / "outward_witness_bundle.json").exists()
    assert (output / "ledger_export.json").exists()
    assert (output / "artifacts" / "committed_output").read_text(encoding="utf-8") == "model approved content"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_package_producer_output_verifies_offline(tmp_path: Path) -> None:
    """Layer: integration. Verifies producer output is accepted by the offline package verifier."""
    db_path = tmp_path / "outward.sqlite3"
    workspace_root = tmp_path
    await _seed_approved_run(db_path, workspace_root)
    output = tmp_path / "package"

    await build_outward_run_witness_package(
        db_path=db_path,
        workspace_root=workspace_root,
        run_id="run-producer",
        output_dir=output,
    )
    report = verify_package(output)

    assert report["result"] == "accepted"
    assert report["missing_evidence"] == []


@pytest.mark.contract
def test_package_producer_cli_emits_package(tmp_path: Path) -> None:
    """Layer: contract. Verifies the producer command accepts run id, db path, workspace root, and output."""
    db_path = tmp_path / "outward.sqlite3"
    workspace_root = tmp_path
    asyncio.run(_seed_approved_run(db_path, workspace_root))
    output = tmp_path / "package"

    exit_code = main(
        [
            "--run-id",
            "run-producer",
            "--db-path",
            str(db_path),
            "--workspace-root",
            str(workspace_root),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert verify_package(output)["result"] == "accepted"


async def _seed_approved_run(db_path: Path, workspace_root: Path) -> None:
    run_id = "run-producer"
    namespace = "issue_run-producer"
    target = workspace_root / "approved.txt"
    target.write_text("model approved content", encoding="utf-8")
    model_dir = workspace_root / "workspace" / namespace / "runs" / run_id
    model_dir.mkdir(parents=True)
    invocation_ref = f"workspace/{namespace}/runs/{run_id}/model_invocation_turn_1.json"
    _write_json(model_dir / "model_invocation_turn_1.json", {"schema_version": "outward_model_invocation.v1", "run_id": run_id})
    _write_json(model_dir / "model_prompt_redacted_turn_1.json", {"schema_version": "outward_model_prompt_redacted.v1", "run_id": run_id})
    _write_json(model_dir / "proposal_extraction_turn_1.json", {"schema_version": "outward_proposal_extraction.v1", "run_id": run_id})
    invocation_digest = _sha256(model_dir / "model_invocation_turn_1.json")
    prompt_digest = _sha256(model_dir / "model_prompt_redacted_turn_1.json")
    extraction_digest = _sha256(model_dir / "proposal_extraction_turn_1.json")
    tool_args = {"path": "approved.txt", "content": "model approved content"}
    digest = args_hash(tool_args)
    proposal_id = f"proposal:{run_id}:write_file:0001"
    run = OutwardRunRecord(
        run_id=run_id,
        status="completed",
        namespace=namespace,
        submitted_at="2026-05-02T12:00:00+00:00",
        started_at="2026-05-02T12:00:01+00:00",
        completed_at="2026-05-02T12:00:09+00:00",
        current_turn=1,
        max_turns=1,
        task={
            "description": "Write approved file",
            "instruction": "Call write_file",
            "acceptance_contract": {"governed_tool_call": {"tool": "write_file", "args": tool_args}},
            "_outward_execution_state": {
                "tool_results": [
                    {"turn": 1, "step_index": 0, "proposal_id": proposal_id, "tool": "write_file", "result": {"ok": True, "path": str(target)}}
                ]
            },
        },
        policy_overrides={"approval_required_tools": ["write_file"], "approval_timeout_seconds": 30, "max_turns": 1},
    )
    await OutwardRunStore(db_path).create(run)
    await OutwardApprovalStore(db_path).save(
        OutwardApprovalProposal(
            proposal_id=proposal_id,
            run_id=run_id,
            namespace=namespace,
            tool="write_file",
            args_preview={"path": "approved.txt", "content": "[REDACTED]"},
            context_summary="model-produced governed tool call from live provider response",
            risk_level="write",
            submitted_at="2026-05-02T12:00:04+00:00",
            expires_at="2026-05-02T12:01:04+00:00",
            status="approved",
            operator_ref="operator:test",
            decision="approve",
            decided_at="2026-05-02T12:00:05+00:00",
        )
    )
    event_store = OutwardRunEventStore(db_path)
    for event_type, turn, payload in [
        ("run_submitted", 0, {"run_id": run_id, "namespace": namespace, "status": "queued", "submitted_at": run.submitted_at, "task_description": run.task["description"], "policy_overrides": run.policy_overrides}),
        ("run_started", 0, {"run_id": run_id, "status": "running", "started_at": run.started_at}),
        ("turn_started", 1, {"run_id": run_id, "turn": 1, "agent_id": "outward-agent"}),
        (
            "proposal_made",
            1,
            {
                "run_id": run_id,
                "namespace": namespace,
                "tool": "write_file",
                "tool_name": "write_file",
                "tool_args_hash": digest,
                "model_invocation_ref": invocation_ref,
                "model_invocation_sha256": invocation_digest,
                "model_prompt_redacted_sha256": prompt_digest,
                "model_response_content_sha256": "response-content-digest",
                "proposal_extraction_sha256": extraction_digest,
                "provider_name": "fake-provider",
                "model_name": "fake-model",
            },
        ),
        ("proposal_pending_approval", 1, {"proposal_id": proposal_id, "run_id": run_id, "tool": "write_file", "tool_args_hash": digest}),
        ("proposal_approved", 1, {"proposal_id": proposal_id, "run_id": run_id, "tool": "write_file", "tool_args_hash": digest}),
        ("tool_invoked", 1, {"connector_name": "write_file", "args_hash": digest, "result_summary": {"ok": True, "path": str(target)}, "duration_ms": 0, "outcome": "success"}),
        ("commitment_recorded", 1, {"run_id": run_id, "tool": "write_file", "outcome": "success"}),
        ("turn_completed", 1, {"run_id": run_id, "turn": 1, "outcome": "success"}),
        ("run_completed", 1, {"run_id": run_id, "status": "completed", "outcome": "success", "completed_at": run.completed_at}),
    ]:
        await event_store.append(
            LedgerEvent(
                event_id=f"run:{run_id}:{len(await event_store.list_for_run(run_id)) + 1:04d}:{event_type}",
                event_type=event_type,
                run_id=run_id,
                turn=turn,
                agent_id="outward-agent",
                at=f"2026-05-02T12:00:{len(await event_store.list_for_run(run_id)) + 1:02d}+00:00",
                payload=payload,
            )
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
