# Layer: unit

from __future__ import annotations

import pytest

from orket.core.domain import OperatorCommandClass, OperatorInputClass
from tests.application.test_engine_approvals import (
    _make_engine,
    _seed_tool_approval_reservation,
    _tool_approval_row,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_engine_get_approval_rejects_unsupported_packet1_status() -> None:
    row = _tool_approval_row()
    row["status"] = "approved_with_edits"
    engine = _make_engine(rows=[row])

    with pytest.raises(RuntimeError, match="unsupported Packet 1 status"):
        await engine.get_approval("apr-1")


@pytest.mark.asyncio
async def test_engine_get_approval_rejects_target_projection_drift() -> None:
    row = _tool_approval_row()
    row["payload_json"] = {
        **dict(row["payload_json"]),
        "control_plane_target_ref": "turn-tool-run:sess-1:ISS-1:coder:9999",
    }
    engine = _make_engine(rows=[row])
    await _seed_tool_approval_reservation(engine)

    with pytest.raises(RuntimeError, match="target projection drift"):
        await engine.get_approval("apr-1")


@pytest.mark.asyncio
async def test_engine_get_approval_rejects_conflicting_operator_action_projection() -> None:
    row = _tool_approval_row()
    row["status"] = "approved"
    engine = _make_engine(rows=[row])
    await engine.control_plane_publication.publish_operator_action(
        action_id="approval-op-1",
        actor_ref="api_key_fingerprint:sha256:test",
        input_class=OperatorInputClass.COMMAND,
        target_ref="approval-request:apr-1",
        timestamp="2026-03-31T18:00:00+00:00",
        precondition_basis_ref="tool_approval-gate:apr-1:resolve",
        result="denied",
        command_class=OperatorCommandClass.MARK_TERMINAL,
        receipt_refs=["approval-request:apr-1"],
    )

    with pytest.raises(RuntimeError, match="conflicting control_plane_operator_action result 'denied'"):
        await engine.get_approval("apr-1")
