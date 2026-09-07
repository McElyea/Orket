from __future__ import annotations

from pathlib import Path

import pytest

from orket.quickstart.ledger import (
    QuickstartLedgerWriter,
    build_event,
    canonical_json,
    compute_event_hash,
    load_ledger_events,
    verify_ledger_events,
)
from orket.quickstart.verify_ledger import main as verify_ledger_main


def _timestamp_factory():
    counter = 0

    def _next() -> str:
        nonlocal counter
        counter += 1
        return f"2026-05-25T00:00:{counter:02d}Z"

    return _next


def _event_chain(event_types: list[str]) -> list[dict]:
    previous_event_hash: str | None = None
    events: list[dict] = []
    for sequence, event_type in enumerate(event_types, start=1):
        event = build_event(
            run_id="run-ledger-test",
            sequence=sequence,
            event_type=event_type,
            timestamp_utc=f"2026-05-25T00:00:{sequence:02d}Z",
            payload={"event_type": event_type},
            previous_event_hash=previous_event_hash,
        )
        previous_event_hash = event["event_hash"]
        events.append(event)
    return events


def test_event_hash_uses_canonical_json_without_event_hash() -> None:
    """Layer: unit. Proves quickstart event hashes are deterministic over canonical event content."""
    event = build_event(
        run_id="run-ledger-test",
        sequence=1,
        event_type="run_started",
        timestamp_utc="2026-05-25T00:00:01Z",
        payload={"b": 2, "a": 1},
        previous_event_hash=None,
    )

    with_changed_hash = dict(event)
    with_changed_hash["event_hash"] = "not-the-real-hash"

    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert compute_event_hash(with_changed_hash) == event["event_hash"]


@pytest.mark.asyncio
async def test_ledger_writer_persists_valid_hash_chain(tmp_path: Path) -> None:
    """Layer: integration. Proves the JSONL writer emits a verifiable linked ledger on disk."""
    ledger_path = tmp_path / "ledger.jsonl"
    writer = await QuickstartLedgerWriter.create(
        path=ledger_path,
        run_id="run-ledger-test",
        timestamp_factory=_timestamp_factory(),
    )

    await writer.emit("run_started", {"demo": "quickstart"})
    await writer.emit("tool_call_proposed", {"tool_name": "write_file"})
    await writer.emit("run_finished", {"terminal_status": "approved_executed"})

    events = await load_ledger_events(ledger_path)
    result = verify_ledger_events(events)

    assert result.valid is True
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert events[0]["previous_event_hash"] is None
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]
    assert events[2]["previous_event_hash"] == events[1]["event_hash"]


def test_verifier_rejects_tampered_event_content() -> None:
    """Layer: contract. Proves changed event content invalidates the stored event hash."""
    events = _event_chain(["run_started", "tool_call_proposed", "run_finished"])
    events[1]["payload"] = {"tool_name": "different_tool"}

    result = verify_ledger_events(events)

    assert result.valid is False
    assert "event[1].event_hash mismatch" in result.errors


def test_verifier_rejects_reordered_events() -> None:
    """Layer: contract. Proves event ordering is part of the verified chain."""
    events = _event_chain(["run_started", "tool_call_proposed", "approval_requested"])
    reordered = [events[0], events[2], events[1]]

    result = verify_ledger_events(reordered)

    assert result.valid is False
    assert any("sequence" in error or "previous_event_hash" in error for error in result.errors)


def test_verifier_rejects_previous_hash_and_event_hash_tamper() -> None:
    """Layer: contract. Proves direct hash-field changes invalidate the ledger."""
    previous_hash_events = _event_chain(["run_started", "tool_call_proposed", "run_finished"])
    previous_hash_events[1]["previous_event_hash"] = "0" * 64

    previous_hash_result = verify_ledger_events(previous_hash_events)

    assert previous_hash_result.valid is False
    assert "event[1].previous_event_hash must equal the prior event_hash" in previous_hash_result.errors
    assert "event[1].event_hash mismatch" in previous_hash_result.errors

    event_hash_events = _event_chain(["run_started", "tool_call_proposed", "run_finished"])
    event_hash_events[1]["event_hash"] = "0" * 64

    event_hash_result = verify_ledger_events(event_hash_events)

    assert event_hash_result.valid is False
    assert "event[1].event_hash mismatch" in event_hash_result.errors
    assert "event[2].previous_event_hash must equal the prior event_hash" in event_hash_result.errors


def test_verify_ledger_cli_reports_success_and_tamper_failure(tmp_path: Path, capsys) -> None:
    """Layer: end-to-end. Proves the module verifier exits zero for valid JSONL and nonzero after tamper."""
    ledger_path = tmp_path / "ledger.jsonl"
    events = _event_chain(["run_started", "tool_call_proposed", "run_finished"])
    ledger_path.write_text("\n".join(canonical_json(event) for event in events) + "\n", encoding="utf-8")

    assert verify_ledger_main([str(ledger_path)]) == 0
    assert "Ledger verification succeeded" in capsys.readouterr().out

    events[1]["sequence"] = 99
    ledger_path.write_text("\n".join(canonical_json(event) for event in events) + "\n", encoding="utf-8")

    assert verify_ledger_main([str(ledger_path)]) == 1
    captured = capsys.readouterr()
    assert "Ledger verification failed" in captured.err
