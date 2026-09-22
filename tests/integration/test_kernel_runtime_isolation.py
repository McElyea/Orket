"""Layer: integration. Independent real application roots cannot share Kernel authority."""

import asyncio

import pytest

from tests.helpers.kernel_state_probe import kernel_app
from tests.integration.test_kernel_publication_input_capture import hold_first_lookup

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("kernel_enabled")]


@pytest.fixture
def kernel_enabled(monkeypatch):
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "false")


def request(**flags):
    return {
        "contract_version": "kernel_api/v1",
        "session_id": "same-session",
        "trace_id": "same-trace",
        "proposal": {"proposal_type": "action.tool_call", "payload": {"tool_name": "local.echo", **flags}},
    }


@pytest.mark.parametrize("surface", ["ledger", "approval-read", "approval-decision", "commit"])
async def test_separate_application_cannot_use_another_kernel_state(tmp_path, surface):
    roots = [tmp_path / name for name in ("first", "second")]
    for root in roots:
        await asyncio.to_thread(root.mkdir)
    first, second = [kernel_app(root) for root in roots]
    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        left, right = first.state.api_runtime_context.engine, second.state.api_runtime_context.engine
        payload = request(approval_required_credentialed=surface.startswith("approval"))
        admitted = await left.kernel_admit_proposal_async(payload)
        if surface == "ledger":
            rows = await asyncio.to_thread(right.kernel_list_ledger_events, payload)
            assert rows["items"] == []
        elif surface == "approval-read":
            assert await right.get_approval(admitted["approval_id"]) is None
        elif surface == "approval-decision":
            with pytest.raises(ValueError, match="not found"):
                await right.decide_approval(approval_id=admitted["approval_id"], decision="approve")
            assert (await left.get_approval(admitted["approval_id"]))["status"] == "PENDING"
        else:
            result = await asyncio.to_thread(
                right.kernel_commit_proposal,
                {
                    **payload,
                    "proposal_digest": admitted["proposal_digest"],
                    "admission_decision_digest": admitted["decision_digest"],
                    "canonical_state_digest_after": "foreign-state",
                },
            )
            assert result["status"] == "REJECTED_PRECONDITION"
            rows = await asyncio.to_thread(left.kernel_list_ledger_events, payload)
            assert not any(row["event_type"] == "commit.recorded" for row in rows["items"])


async def test_closed_engine_refuses_kernel_mutation(tmp_path):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        await engine.close()
        with pytest.raises(RuntimeError, match="clos"):
            await engine.kernel_admit_proposal_async(request())


async def test_engine_close_joins_admitted_kernel_publication(tmp_path, monkeypatch):
    app = kernel_app(tmp_path)
    async with app.router.lifespan_context(app):
        engine = app.state.api_runtime_context.engine
        entered, release = hold_first_lookup(monkeypatch, engine.control_plane_execution_repository)
        active = asyncio.create_task(engine.kernel_admit_proposal_async(request()))
        closing = None
        try:
            await asyncio.wait_for(entered.wait(), 10)
            closing = asyncio.create_task(engine.close())
            await asyncio.sleep(0.03)
            assert not closing.done() and not engine._closed and not active.done()
            release.set()
            outcomes = await asyncio.wait_for(asyncio.gather(active, closing, return_exceptions=True), 10)
            assert isinstance(outcomes[0], (dict, asyncio.CancelledError)) and outcomes[1] is None
            assert engine._closed
            run = await engine.control_plane_execution_repository.get_run_record(
                run_id="kernel-action-run:same-session:same-trace"
            )
            assert run is not None
        finally:
            release.set()
            await asyncio.gather(active, *([closing] if closing else []), return_exceptions=True)
