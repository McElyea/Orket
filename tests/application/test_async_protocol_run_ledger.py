from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.workflows.tool_invocation_contracts import (
    PROTOCOL_RECEIPT_SCHEMA_VERSION,
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)


def _tool_call_payload(
    *,
    session_id: str,
    operation_id: str,
    tool_name: str = "write_file",
    tool_args: dict | None = None,
) -> dict:
    args = dict(tool_args or {"path": f"agent_output/{operation_id}.txt", "content": "ok"})
    manifest = build_tool_invocation_manifest(run_id=session_id, tool_name=tool_name)
    return {
        "operation_id": operation_id,
        "tool": tool_name,
        "tool_args": args,
        "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name=tool_name,
            tool_args=args,
            tool_contract_version=str(manifest["tool_contract_version"]),
            capability_profile=str(manifest["capability_profile"]),
        ),
    }


def _tool_result_payload(
    *,
    call_payload: dict,
    call_sequence_number: int,
    result: dict,
    step_id: str | None = None,
) -> dict:
    payload = {
        "operation_id": str(call_payload.get("operation_id") or ""),
        "tool": str(call_payload.get("tool") or ""),
        "result": dict(result or {}),
        "call_sequence_number": int(call_sequence_number),
        "tool_invocation_manifest": dict(call_payload.get("tool_invocation_manifest") or {}),
        "tool_call_hash": str(call_payload.get("tool_call_hash") or ""),
    }
    if step_id:
        payload["step_id"] = step_id
    return payload


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_start_and_finalize(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-1",
        run_type="epic",
        run_name="Epic One",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/path"},
    )
    await repo.finalize_run(
        session_id="sess-1",
        status="incomplete",
        summary={"session_status": "incomplete"},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )

    run = await repo.get_run("sess-1")
    assert run is not None
    assert run["session_id"] == "sess-1"
    assert run["run_type"] == "epic"
    assert run["run_name"] == "Epic One"
    assert run["status"] == "incomplete"
    assert run["summary_json"]["session_status"] == "incomplete"
    assert run["artifact_json"]["workspace"] == "workspace/path"
    assert run["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert run["started_event_seq"] == 1
    assert run["ended_event_seq"] == 2
    events = await repo.list_events("sess-1")
    assert events[0]["ledger_schema_version"] == "1.0"
    assert events[0]["run_id"] == "sess-1"
    assert events[0]["event_type"] == "run_started"
    assert events[0]["sequence_number"] == events[0]["event_seq"]
    assert str(events[0]["timestamp"]).strip() != ""
    assert events[1]["event_type"] == "run_finalized"
    assert events[1]["sequence_number"] == events[1]["event_seq"]


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_start_and_finalize_are_idempotent(tmp_path: Path) -> None:
    """Layer: integration. Verifies crash recovery replays do not duplicate lifecycle records."""
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-idempotent",
        run_type="epic",
        run_name="Idempotent",
        department="core",
        build_id="build-1",
    )
    await repo.start_run(
        session_id="sess-idempotent",
        run_type="epic",
        run_name="Idempotent",
        department="core",
        build_id="build-1",
    )
    await repo.finalize_run(session_id="sess-idempotent", status="incomplete")
    await repo.finalize_run(session_id="sess-idempotent", status="incomplete")

    events = await repo.list_events("sess-idempotent")
    assert [event["kind"] for event in events] == ["run_started", "run_finalized"]


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_finalize_rejects_done_with_failure(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-invariant",
        run_type="epic",
        run_name="Invariant",
        department="core",
        build_id="build-invariant",
    )
    with pytest.raises(ValueError, match="E_RESULT_ERROR_INVARIANT:done_must_not_have_failure"):
        await repo.finalize_run(
            session_id="sess-invariant",
            status="done",
            failure_class="ExecutionFailed",
            failure_reason="should not be present on done",
        )


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_event_is_monotonic(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first = await repo.append_event(session_id="sess-2", kind="event_a", payload={"x": 1})
    second = await repo.append_event(session_id="sess-2", kind="event_b", payload={"x": 2})
    events = await repo.list_events("sess-2")
    assert first["event_seq"] == 1
    assert second["event_seq"] == 2
    assert first["sequence_number"] == 1
    assert second["sequence_number"] == 2
    assert first["ledger_schema_version"] == "1.0"
    assert first["run_id"] == "sess-2"
    assert [row["event_seq"] for row in events] == [1, 2]
    assert [row["sequence_number"] for row in events] == [1, 2]
    assert [row["kind"] for row in events] == ["event_a", "event_b"]


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_returns_none_for_missing_run(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    run = await repo.get_run("missing")
    assert run is None


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_isolated_by_session(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-a",
        run_type="epic",
        run_name="A",
        department="core",
        build_id="build-a",
    )
    await repo.start_run(
        session_id="sess-b",
        run_type="epic",
        run_name="B",
        department="core",
        build_id="build-b",
    )
    events_a = await repo.list_events("sess-a")
    events_b = await repo.list_events("sess-b")
    assert len(events_a) == 1
    assert len(events_b) == 1
    assert events_a[0]["session_id"] == "sess-a"
    assert events_b[0]["session_id"] == "sess-b"


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_operation_commit_is_first_wins(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-op", operation_id="op-1")
    call = await repo.append_event(
        session_id="sess-op",
        kind="tool_call",
        payload=call_payload,
    )
    first = await repo.append_event(
        session_id="sess-op",
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call["event_seq"]),
            result={"ok": True, "value": 1},
        ),
    )
    second = await repo.append_event(
        session_id="sess-op",
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call["event_seq"]),
            result={"ok": True, "value": 2},
        ),
    )
    assert first["event_seq"] == 2
    assert second["kind"] == "operation_rejected"
    assert second["error_code"] == "E_DUPLICATE_OPERATION"
    assert second["winner_event_seq"] == 2
    assert second["idempotent_reuse"] is False


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_duplicate_same_payload_marks_idempotent_reuse(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-op-idem", operation_id="op-1")
    call = await repo.append_event(
        session_id="sess-op-idem",
        kind="tool_call",
        payload=call_payload,
    )
    first_payload = _tool_result_payload(
        call_payload=call_payload,
        call_sequence_number=int(call["event_seq"]),
        result={"ok": True, "value": 1},
    )
    _ = await repo.append_event(session_id="sess-op-idem", kind="operation_result", payload=first_payload)
    second = await repo.append_event(session_id="sess-op-idem", kind="operation_result", payload=first_payload)
    assert second["kind"] == "operation_rejected"
    assert second["error_code"] == "E_DUPLICATE_OPERATION"
    assert second["idempotent_reuse"] is True


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_event_flattens_payload_fields(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-flat", operation_id="op-flat")
    call = await repo.append_event(
        session_id="sess-flat",
        kind="tool_call",
        payload=call_payload,
    )
    appended = await repo.append_event(
        session_id="sess-flat",
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call["event_seq"]),
            result={"ok": True, "value": 9},
            step_id="ISSUE-1:1",
        ),
    )
    assert appended["kind"] == "operation_result"
    assert appended["operation_id"] == "op-flat"
    assert appended["tool"] == "write_file"
    assert appended["tool_name"] == "write_file"
    assert appended["result"]["ok"] is True
    events = await repo.list_events("sess-flat")
    assert events[1]["operation_id"] == "op-flat"
    assert events[1]["step_id"] == "ISSUE-1:1"


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_assigns_seq_and_digest(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first = await repo.append_receipt(
        session_id="sess-receipt",
        receipt={
            "run_id": "sess-receipt",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "event_seq_range": [1, 1],
            "execution_result": {"ok": True},
        },
    )
    second = await repo.append_receipt(
        session_id="sess-receipt",
        receipt={
            "run_id": "sess-receipt",
            "step_id": "ISSUE-1:2",
            "operation_id": "op-2",
            "event_seq_range": [2, 2],
            "execution_result": {"ok": True},
        },
    )
    assert first["receipt_seq"] == 1
    assert second["receipt_seq"] == 2
    assert first["schema_version"] == PROTOCOL_RECEIPT_SCHEMA_VERSION
    assert second["schema_version"] == PROTOCOL_RECEIPT_SCHEMA_VERSION
    assert len(str(first["receipt_digest"])) == 64
    assert len(str(second["receipt_digest"])) == 64
    rows = await repo.list_receipts("sess-receipt")
    assert [row["receipt_seq"] for row in rows] == [1, 2]
    assert [row["schema_version"] for row in rows] == [
        PROTOCOL_RECEIPT_SCHEMA_VERSION,
        PROTOCOL_RECEIPT_SCHEMA_VERSION,
    ]


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_dedupes_existing_digest(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    payload = {
        "run_id": "sess-receipt-idem",
        "step_id": "ISSUE-1:1",
        "operation_id": "op-1",
        "event_seq_range": [1, 1],
        "execution_result": {"ok": True},
    }
    first = await repo.append_receipt(session_id="sess-receipt-idem", receipt=payload)
    second = await repo.append_receipt(session_id="sess-receipt-idem", receipt=payload)
    assert first["receipt_seq"] == 1
    assert second["receipt_seq"] == 1
    rows = await repo.list_receipts("sess-receipt-idem")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_rejects_non_monotonic_seq(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.append_receipt(
        session_id="sess-receipt-seq",
        receipt={
            "run_id": "sess-receipt-seq",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "event_seq_range": [1, 1],
            "execution_result": {"ok": True},
            "receipt_seq": 1,
        },
    )
    with pytest.raises(ValueError, match="E_RECEIPT_SEQ_NON_MONOTONIC"):
        await repo.append_receipt(
            session_id="sess-receipt-seq",
            receipt={
                "run_id": "sess-receipt-seq",
                "step_id": "ISSUE-1:2",
                "operation_id": "op-2",
                "event_seq_range": [2, 2],
                "execution_result": {"ok": True},
                "receipt_seq": 1,
            },
        )


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_enforces_max_tool_invocations_per_run(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path, max_tool_invocations_per_run=2)
    call_payload = _tool_call_payload(session_id="sess-limit", operation_id="op-1")
    first = await repo.append_event(
        session_id="sess-limit",
        kind="tool_call",
        payload=call_payload,
    )
    second = await repo.append_event(
        session_id="sess-limit",
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(first["event_seq"]),
            result={"ok": True},
        ),
    )
    third = await repo.append_event(
        session_id="sess-limit",
        kind="tool_call",
        payload=_tool_call_payload(session_id="sess-limit", operation_id="op-2"),
    )

    assert first["kind"] == "tool_call"
    assert second["kind"] == "operation_result"
    assert third["kind"] == "tool_invocation_rejected"
    assert third["error_code"] == "E_MAX_TOOL_INVOCATIONS_EXCEEDED"
    assert third["max_tool_invocations_per_run"] == 2
    events = await repo.list_events("sess-limit")
    assert len(events) == 2


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_event_ignores_protected_payload_fields(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    appended = await repo.append_event(
        session_id="sess-protected",
        kind="event_a",
        payload={
            "run_id": "forged",
            "session_id": "forged",
            "ledger_schema_version": "9.9",
            "event_type": "forged",
            "sequence_number": 999,
            "event_seq": 999,
            "timestamp": "1970-01-01T00:00:00+00:00",
            "x": 1,
        },
    )

    assert appended["run_id"] == "sess-protected"
    assert appended["session_id"] == "sess-protected"
    assert appended["ledger_schema_version"] == "1.0"
    assert appended["event_type"] == "event_a"
    assert appended["sequence_number"] == 1
    assert appended["event_seq"] == 1
    assert appended["timestamp"] != "1970-01-01T00:00:00+00:00"
    assert appended["x"] == 1


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_rejects_non_monotonic_timestamps(tmp_path: Path, monkeypatch) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    _ = await repo.append_event(session_id="sess-ts", kind="event_a", payload={"x": 1})

    def _fake_build_event(*, session_id: str, kind: str, event_type: str, **extra):
        return {
            "ledger_schema_version": "1.0",
            "kind": kind,
            "event_type": event_type,
            "session_id": session_id,
            "run_id": session_id,
            "timestamp": "1970-01-01T00:00:00+00:00",
            "tool_name": "",
            **dict(extra),
        }

    monkeypatch.setattr(repo, "_build_event", _fake_build_event)

    with pytest.raises(ValueError, match="E_LEDGER_TIMESTAMP_NON_MONOTONIC"):
        _ = await repo.append_event(session_id="sess-ts", kind="event_b", payload={"x": 2})


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_accepts_later_timestamp_with_different_offset_format(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    timestamps = iter(
        [
            "2025-01-01T00:30:00+01:00",
            "2025-01-01T00:00:00Z",
        ]
    )
    original_build_event = repo._build_event

    def _fake_build_event(*, session_id: str, kind: str, event_type: str, **extra):
        event = original_build_event(session_id=session_id, kind=kind, event_type=event_type, **extra)
        event["timestamp"] = next(timestamps)
        return event

    monkeypatch.setattr(repo, "_build_event", _fake_build_event)

    first = await repo.append_event(session_id="sess-ts-offset", kind="event_a", payload={"x": 1})
    second = await repo.append_event(session_id="sess-ts-offset", kind="event_b", payload={"x": 2})

    assert first["event_seq"] == 1
    assert second["event_seq"] == 2


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_get_run_returns_none_without_run_started(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    _ = await repo.append_event(session_id="sess-no-start", kind="tool_call", payload=_tool_call_payload(session_id="sess-no-start", operation_id="op-1"))

    run = await repo.get_run("sess-no-start")

    assert run is None


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_adds_tool_invocation_manifest_for_tool_events(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-manifest", operation_id="op-1")
    call_payload["tool_invocation_manifest"] = build_tool_invocation_manifest(
        run_id="sess-manifest",
        tool_name="write_file",
        control_plane_run_id="turn-tool-run:sess-manifest:ISSUE-1:coder:0001",
        control_plane_attempt_id="turn-tool-run:sess-manifest:ISSUE-1:coder:0001:attempt:0001",
        control_plane_step_id="op-1",
        control_plane_reservation_id="turn-tool-reservation:turn-tool-run:sess-manifest:ISSUE-1:coder:0001",
        control_plane_lease_id="turn-tool-lease:turn-tool-run:sess-manifest:ISSUE-1:coder:0001",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    appended = await repo.append_event(
        session_id="sess-manifest",
        kind="tool_call",
        payload=call_payload,
    )

    manifest = appended["tool_invocation_manifest"]
    assert manifest["tool_name"] == "write_file"
    assert manifest["run_id"] == "sess-manifest"
    assert manifest["determinism_class"] == "workspace"
    assert manifest["control_plane_run_id"] == "turn-tool-run:sess-manifest:ISSUE-1:coder:0001"
    assert manifest["control_plane_attempt_id"] == "turn-tool-run:sess-manifest:ISSUE-1:coder:0001:attempt:0001"
    assert manifest["control_plane_step_id"] == "op-1"
    assert (
        manifest["control_plane_reservation_id"]
        == "turn-tool-reservation:turn-tool-run:sess-manifest:ISSUE-1:coder:0001"
    )
    assert manifest["control_plane_lease_id"] == "turn-tool-lease:turn-tool-run:sess-manifest:ISSUE-1:coder:0001"
    assert manifest["control_plane_resource_id"] == "namespace:issue:ISSUE-1"
    assert len(str(manifest["manifest_hash"])) == 64
    assert len(str(appended["tool_call_hash"])) == 64


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_rejects_invalid_tool_invocation_manifest(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    rejected = await repo.append_event(
        session_id="sess-manifest-invalid",
        kind="tool_call",
        payload={
            "operation_id": "op-1",
            "tool_invocation_manifest": {
                "tool_name": "",
                "run_id": "sess-manifest-invalid",
                "ring": "core",
                "determinism_class": "workspace",
            },
        },
    )

    assert rejected["kind"] == "tool_invocation_rejected"
    assert rejected["error_code"] == "E_TOOL_INVOCATION_MANIFEST_INVALID"


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_requires_manifest_for_tool_invocation_events(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    rejected = await repo.append_event(
        session_id="sess-manifest-required",
        kind="tool_call",
        payload={"operation_id": "op-1", "tool": "write_file", "tool_args": {"path": "a.txt"}},
    )
    assert rejected["kind"] == "tool_invocation_rejected"
    assert rejected["error_code"] == "E_TOOL_INVOCATION_MANIFEST_INVALID"


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_requires_call_sequence_for_result_events(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-call-seq", operation_id="op-1")
    _ = await repo.append_event(session_id="sess-call-seq", kind="tool_call", payload=call_payload)
    rejected = await repo.append_event(
        session_id="sess-call-seq",
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": True},
            "tool_invocation_manifest": dict(call_payload["tool_invocation_manifest"]),
            "tool_call_hash": str(call_payload["tool_call_hash"]),
        },
    )
    assert rejected["kind"] == "ledger_contract_rejected"
    assert rejected["error_code"] == "E_CALL_SEQUENCE_REQUIRED"


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_rejects_artifact_emission_before_result(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-artifact-before-result", operation_id="op-1")
    call = await repo.append_event(
        session_id="sess-artifact-before-result",
        kind="tool_call",
        payload=call_payload,
    )
    rejected = await repo.append_event(
        session_id="sess-artifact-before-result",
        kind="artifact_emitted",
        payload={
            "call_sequence_number": int(call["event_seq"]),
            "artifact_hash": "a" * 64,
            "artifact_path": "runs/sess-artifact-before-result/out.txt",
        },
    )
    assert rejected["kind"] == "ledger_contract_rejected"
    assert rejected["error_code"] == "E_ARTIFACT_EMIT_BEFORE_RESULT"


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_allows_artifact_emission_after_result(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    call_payload = _tool_call_payload(session_id="sess-artifact-after-result", operation_id="op-1")
    call = await repo.append_event(
        session_id="sess-artifact-after-result",
        kind="tool_call",
        payload=call_payload,
    )
    result = await repo.append_event(
        session_id="sess-artifact-after-result",
        kind="operation_result",
        payload=_tool_result_payload(
            call_payload=call_payload,
            call_sequence_number=int(call["event_seq"]),
            result={"ok": True},
        ),
    )
    appended = await repo.append_event(
        session_id="sess-artifact-after-result",
        kind="artifact_emitted",
        payload={
            "call_sequence_number": int(call["event_seq"]),
            "artifact_hash": "b" * 64,
            "artifact_path": "runs/sess-artifact-after-result/out.txt",
        },
    )
    assert result["kind"] == "operation_result"
    assert appended["kind"] == "artifact_emitted"
    assert appended["call_sequence_number"] == int(call["event_seq"])
    assert appended["artifact_hash"] == "b" * 64


# Layer: contract
@pytest.mark.asyncio
async def test_async_protocol_run_ledger_rejects_finalize_when_tool_call_orphaned(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-orphan",
        run_type="epic",
        run_name="Orphan",
        department="core",
        build_id="build-orphan",
    )
    _ = await repo.append_event(
        session_id="sess-orphan",
        kind="tool_call",
        payload=_tool_call_payload(session_id="sess-orphan", operation_id="op-1"),
    )
    with pytest.raises(ValueError, match="E_ORPHANED_TOOL_CALL"):
        await repo.finalize_run(session_id="sess-orphan", status="failed")
