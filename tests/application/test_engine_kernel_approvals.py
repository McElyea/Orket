"""Layer: unit. Explicit engine ownership with in-memory approval publication ports."""

from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from tests.application.test_engine_approvals import _make_engine

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
# Layer: unit
async def test_engine_approvals_use_nervous_system_runtime_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    engine = _make_engine()
    await run_owned_thread(
        partial(
            engine.kernel_gateway.admit_proposal,
            {
                "contract_version": "kernel_api/v1",
                "session_id": "sess-ns-engine-1",
                "trace_id": "trace-ns-engine-1",
                "proposal": {
                    "proposal_type": "action.tool_call",
                    "payload": {"approval_required_destructive": True},
                },
            },
        ),
        label="seed-approval",
    )
    items = await engine.list_approvals(status="PENDING", session_id="sess-ns-engine-1", limit=10)
    assert len(items) == 1
    approval_id = items[0]["approval_id"]

    resolved = await engine.decide_approval(
        approval_id=approval_id,
        decision="approve",
        operator_actor_ref="api_key_fingerprint:sha256:test",
    )
    assert resolved["approval"]["status"] == "APPROVED"
    assert resolved["approval"]["control_plane_operator_action"]["result"] == "approved"
    actions = await engine.control_plane_repository.list_operator_actions(target_ref=f"approval-request:{approval_id}")
    assert len(actions) == 1
