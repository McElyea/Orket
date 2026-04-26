from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_ledger_service import OutwardLedgerService, verify_ledger_export
from orket.application.services.outward_run_service import OutwardRunService
from orket.core.domain.outward_run_events import LedgerEvent


async def _seed_completed_run(db_path) -> None:
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    run = await OutwardRunService(
        run_store=run_store,
        event_store=event_store,
        run_id_factory=lambda: "generated",
        utc_now=lambda: "2026-04-25T12:00:00+00:00",
    ).submit({"run_id": "run-ledger", "task": {"description": "Ledger", "instruction": "Prove ledger"}})
    await event_store.append(
        LedgerEvent(
            event_id="run:run-ledger:0300:proposal:write_file",
            event_type="proposal_made",
            run_id="run-ledger",
            turn=1,
            agent_id="outward-agent",
            at="2026-04-25T12:00:10+00:00",
            payload={"tool": "write_file", "args_preview": {"path": "out.txt"}},
        )
    )
    await event_store.append(
        LedgerEvent(
            event_id="proposal:run-ledger:write_file:0001:0002:proposal_approved",
            event_type="proposal_approved",
            run_id="run-ledger",
            turn=1,
            agent_id="operator",
            at="2026-04-25T12:00:20+00:00",
            payload={"proposal_id": "proposal:run-ledger:write_file:0001", "operator_ref": "operator:test"},
        )
    )
    await event_store.append(
        LedgerEvent(
            event_id="run:run-ledger:0400:tool:write_file",
            event_type="tool_invoked",
            run_id="run-ledger",
            turn=1,
            agent_id="outward-agent",
            at="2026-04-25T12:00:30+00:00",
            payload={"connector_name": "write_file", "outcome": "success"},
        )
    )
    await event_store.append(
        LedgerEvent(
            event_id="run:run-ledger:0500:commitment:write_file",
            event_type="commitment_recorded",
            run_id="run-ledger",
            turn=1,
            agent_id="outward-agent",
            at="2026-04-25T12:00:40+00:00",
            payload={"tool": "write_file", "outcome": "committed"},
        )
    )
    await run_store.update(replace(run, status="completed", current_turn=1, completed_at="2026-04-25T12:01:00+00:00"))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ledger_export_hashes_full_export_and_detects_payload_tampering(tmp_path) -> None:
    """Layer: integration. Verifies full ledger export hashes stored events and offline verification detects drift."""
    db_path = tmp_path / "phase4-ledger.sqlite3"
    await _seed_completed_run(db_path)
    service = OutwardLedgerService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        utc_now=lambda: "2026-04-25T12:02:00+00:00",
    )

    exported = await service.export("run-ledger")
    verified = verify_ledger_export(exported)
    stored_events = await OutwardRunEventStore(db_path).list_for_run("run-ledger")
    tampered = deepcopy(exported)
    tampered["events"][0]["payload"]["task_description"] = "changed"

    assert exported["schema_version"] == "ledger_export.v1"
    assert exported["export_scope"] == "all"
    assert exported["summary"]["event_count"] == len(exported["events"])
    assert exported["events"][0]["previous_chain_hash"] == "GENESIS"
    assert stored_events[0].event_hash
    assert stored_events[0].chain_hash
    assert verified["result"] == "valid"
    assert verify_ledger_export(tampered)["result"] == "invalid"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_filtered_ledger_export_is_partial_verified_view_with_anchors(tmp_path) -> None:
    """Layer: integration. Verifies filtered exports report partial validity instead of full-ledger completeness."""
    db_path = tmp_path / "phase4-ledger-partial.sqlite3"
    await _seed_completed_run(db_path)
    service = OutwardLedgerService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        utc_now=lambda: "2026-04-25T12:02:00+00:00",
    )

    exported = await service.export("run-ledger", types=("proposals", "decisions"))
    verified = verify_ledger_export(exported)

    assert exported["export_scope"] == "partial_view"
    assert [event["event_group"] for event in exported["events"]] == ["proposals", "decisions"]
    assert exported["canonical"]["event_count"] > len(exported["events"])
    assert exported["omitted_spans"]
    assert verified["result"] == "partial_valid"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_include_pii_export_records_audit_event_before_serialization(tmp_path) -> None:
    """Layer: integration. Verifies explicit include-pii export records the named audit ledger event."""
    db_path = tmp_path / "phase4-ledger-audit.sqlite3"
    await _seed_completed_run(db_path)
    service = OutwardLedgerService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        utc_now=lambda: "2026-04-25T12:02:00+00:00",
    )

    exported = await service.export("run-ledger", include_pii=True, record_request=True, operator_ref="operator:test")
    audit_events = [event for event in exported["events"] if event["event_type"] == "ledger_export_requested"]

    assert audit_events
    assert audit_events[0]["event_group"] == "audit"
    assert audit_events[0]["payload"]["include_pii"] is True
    assert audit_events[0]["payload"]["operator_ref"] == "operator:test"
    assert verify_ledger_export(exported)["result"] == "valid"
