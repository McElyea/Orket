from __future__ import annotations

import asyncio
import json
from pathlib import Path

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.workflows.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from scripts.protocol.publish_protocol_rollout_artifacts import main


async def _seed_run(
    *,
    workspace_root: Path,
    sqlite_db: Path,
    run_id: str,
    session_id: str,
    sqlite_status: str,
    protocol_status: str,
    operation_ok: bool,
) -> None:
    sqlite_db.parent.mkdir(parents=True, exist_ok=True)
    protocol_repo = AsyncProtocolRunLedgerRepository(workspace_root)
    sqlite_repo = AsyncRunLedgerRepository(sqlite_db)
    await sqlite_repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Rollout Publish",
        department="core",
        build_id="build-1",
    )
    await sqlite_repo.finalize_run(session_id=session_id, status=sqlite_status)

    await protocol_repo.start_run(
        session_id=run_id,
        run_type="epic",
        run_name="Rollout Publish",
        department="core",
        build_id="build-1",
    )
    manifest = build_tool_invocation_manifest(run_id=run_id, tool_name="write_file")
    tool_args = {"path": f"agent_output/{run_id}.txt", "content": "ok"}
    tool_call_hash = compute_tool_call_hash(
        tool_name="write_file",
        tool_args=tool_args,
        tool_contract_version=str(manifest["tool_contract_version"]),
        capability_profile=str(manifest["capability_profile"]),
    )
    call_event = await protocol_repo.append_event(
        session_id=run_id,
        kind="tool_call",
        payload={
            "operation_id": "op-1",
            "tool": "write_file",
            "tool_args": tool_args,
            "tool_invocation_manifest": manifest,
            "tool_call_hash": tool_call_hash,
        },
    )
    call_seq = int(call_event.get("event_seq") or call_event.get("sequence_number") or 0)
    await protocol_repo.append_event(
        session_id=run_id,
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": operation_ok},
            "call_sequence_number": call_seq,
            "tool_invocation_manifest": manifest,
            "tool_call_hash": tool_call_hash,
        },
    )
    await protocol_repo.finalize_run(
        session_id=run_id,
        status=protocol_status,
        failure_class=None if protocol_status == "incomplete" else "ExecutionFailed",
        failure_reason=None if protocol_status == "incomplete" else "failed",
    )


def test_publish_protocol_rollout_artifacts_writes_latest_bundle(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    sqlite_db = workspace_root / ".orket" / "durable" / "db" / "orket_persistence.db"
    out_dir = tmp_path / "artifacts"
    asyncio.run(
        _seed_run(
            workspace_root=workspace_root,
            sqlite_db=sqlite_db,
            run_id="run-a",
            session_id="run-a",
            sqlite_status="incomplete",
            protocol_status="incomplete",
            operation_ok=True,
        )
    )
    asyncio.run(
        _seed_run(
            workspace_root=workspace_root,
            sqlite_db=sqlite_db,
            run_id="run-b",
            session_id="run-b",
            sqlite_status="incomplete",
            protocol_status="incomplete",
            operation_ok=True,
        )
    )

    exit_code = main(
        [
            "--workspace-root",
            str(workspace_root),
            "--out-dir",
            str(out_dir),
            "--baseline-run-id",
            "run-a",
            "--run-id",
            "run-a",
            "--session-id",
            "run-a",
            "--strict",
        ]
    )
    assert exit_code == 0

    latest_json = out_dir / "protocol_rollout_bundle.latest.json"
    latest_md = out_dir / "protocol_rollout_bundle.latest.md"
    assert latest_json.exists()
    assert latest_md.exists()

    bundle = json.loads(latest_json.read_text(encoding="utf-8"))
    assert bundle["strict_ok"] is True
    assert bundle["replay_campaign"]["all_match"] is True
    assert bundle["ledger_parity_campaign"]["all_match"] is True


def test_publish_protocol_rollout_artifacts_strict_fails_on_mismatch(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    sqlite_db = workspace_root / ".orket" / "durable" / "db" / "orket_persistence.db"
    out_dir = tmp_path / "artifacts"
    asyncio.run(
        _seed_run(
            workspace_root=workspace_root,
            sqlite_db=sqlite_db,
            run_id="run-a",
            session_id="run-a",
            sqlite_status="incomplete",
            protocol_status="incomplete",
            operation_ok=True,
        )
    )
    asyncio.run(
        _seed_run(
            workspace_root=workspace_root,
            sqlite_db=sqlite_db,
            run_id="run-b",
            session_id="run-b",
            sqlite_status="failed",
            protocol_status="failed",
            operation_ok=False,
        )
    )

    exit_code = main(
        [
            "--workspace-root",
            str(workspace_root),
            "--out-dir",
            str(out_dir),
            "--baseline-run-id",
            "run-a",
            "--strict",
        ]
    )
    assert exit_code == 1
