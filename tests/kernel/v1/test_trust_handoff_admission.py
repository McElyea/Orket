from __future__ import annotations

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_service import OutwardRunService
from scripts.proof.trust_handoff_emitter import emit_trust_handoff_package
from tests.helpers.outward_model import patch_outward_model_client


SOURCE_RUN_ID = "run-live-proof"
SOURCE_AGENT_ID = "outward-agent"
SCOPE_ID = "scope-packet1"


def _package(tmp_path, *, target_agent_id: str):
    out = tmp_path / f"handoff-{target_agent_id}"
    emit_trust_handoff_package(
        source_run_id=SOURCE_RUN_ID,
        target_agent_id=target_agent_id,
        scope_id=SCOPE_ID,
        out_dir=out,
    )
    return out


def _payload(run_id: str, package_path, *, complete: bool = True) -> dict:
    acceptance = {
        "handoff_required": True,
        "governed_tool_call": {"tool": "write_file", "args": {"path": "b.txt", "content": "b"}},
    }
    if complete:
        acceptance.update(
            {
                "handoff_policy_compatibility_scope_id": SCOPE_ID,
                "handoff_envelope_package_path": str(package_path),
                "expected_source_agent_id": SOURCE_AGENT_ID,
            }
        )
    return {
        "run_id": run_id,
        "task": {"description": "B consumes A output", "instruction": "Call write_file", "acceptance_contract": acceptance},
        "policy_overrides": {"approval_required_tools": ["write_file"]},
    }


async def _services(tmp_path):
    db_path = tmp_path / "handoff-admission.sqlite3"
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    run_service = OutwardRunService(
        run_store=run_store,
        event_store=event_store,
        run_id_factory=lambda: "generated",
        utc_now=lambda: "2026-05-04T12:00:00+00:00",
    )
    approval_service = OutwardApprovalService(
        approval_store=OutwardApprovalStore(db_path),
        run_store=run_store,
        event_store=event_store,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=lambda: "2026-05-04T12:00:01+00:00",
    )
    execution_service = OutwardRunExecutionService(
        run_store=run_store,
        event_store=event_store,
        approval_service=approval_service,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path,
        utc_now=lambda: "2026-05-04T12:00:02+00:00",
    )
    return run_service, execution_service, event_store


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verified_handoff_admission_precedes_run_start(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies Packet 1 B admission emits trust_handoff_verified before run_started."""
    patch_outward_model_client(monkeypatch, args={"path": "b.txt", "content": "b"})
    package = _package(tmp_path, target_agent_id="run-b-handoff")
    run_service, execution_service, event_store = await _services(tmp_path)

    submitted = await run_service.submit(_payload("run-b-handoff", package))
    started = await execution_service.start_if_ready(submitted.run_id)

    assert started.status == "approval_required"
    events = await event_store.list_for_run("run-b-handoff")
    event_types = [event.event_type for event in events]
    assert event_types.index("trust_handoff_verified") < event_types.index("run_started")
    assert event_types.index("run_started") < event_types.index("turn_started")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incomplete_handoff_contract_rejects_before_start(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies incomplete Packet 1 acceptance fails closed before B starts."""
    patch_outward_model_client(monkeypatch)
    run_service, execution_service, event_store = await _services(tmp_path)

    submitted = await run_service.submit(_payload("run-b-incomplete", tmp_path / "missing", complete=False))
    rejected = await execution_service.start_if_ready(submitted.run_id)

    assert rejected.status == "completed"
    assert rejected.stop_reason == "handoff_acceptance_contract_incomplete"
    event_types = [event.event_type for event in await event_store.list_for_run("run-b-incomplete")]
    assert event_types == ["run_submitted", "trust_handoff_rejected", "run_completed"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_handoff_package_cannot_reach_model_or_effect_paths(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies rejected Packet 1 packages do not start turns, models, tools, or commitments."""
    patch_outward_model_client(monkeypatch)
    package = _package(tmp_path, target_agent_id="run-b-reject")
    (package / "artifacts" / "committed_output").write_bytes(b"tampered")
    run_service, execution_service, event_store = await _services(tmp_path)

    submitted = await run_service.submit(_payload("run-b-reject", package))
    rejected = await execution_service.start_if_ready(submitted.run_id)

    assert rejected.status == "completed"
    assert rejected.stop_reason == "package_digest_mismatch"
    event_types = [event.event_type for event in await event_store.list_for_run("run-b-reject")]
    assert "trust_handoff_rejected" in event_types
    assert not {"run_started", "turn_started", "proposal_made", "tool_invoked", "commitment_recorded"} & set(event_types)
