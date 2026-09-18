"""Layer: contract. Controlled engine/scheduler parity for application run admission."""
from types import SimpleNamespace

import pytest

from orket.application.services.flow_authoring_service import FlowRuntimeNotAdmittedError
from orket.application.services.flow_runtime_service import accept_flow_run
from orket.exceptions import CardNotFound
from tests.helpers.flow_authoring import FlowInputs

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("outcome", ["accepted", "missing", "unresolved", "epic", "schedule_failure"])
async def test_flow_run_admission_preserves_ceiling_and_supplied_acceptance_inputs(outcome):
    scheduled = []

    class Inputs(FlowInputs):
        def create_session_id(self):
            return "captured-session"

    async def prepare(**kwargs):
        assert kwargs == {"flow_id": "FLOW", "expected_revision_id": "frv_1"}
        return "frv_1", "CARD"

    async def get_card(card_id):
        assert card_id == "CARD"
        return None if outcome == "missing" else {"id": card_id}

    async def resolve(card_id):
        assert card_id == "CARD"
        if outcome == "unresolved":
            raise CardNotFound(card_id)
        return ("epic" if outcome == "epic" else "issue"), "parent"

    async def schedule(owner, invocation, mode, session):
        assert owner is engine
        scheduled.append((invocation, mode, session))
        if outcome == "schedule_failure":
            raise RuntimeError("schedule refused")

    engine = SimpleNamespace(cards=SimpleNamespace(get_by_id=get_card), resolve_run_card_target=resolve)
    kwargs = dict(service=SimpleNamespace(prepare_flow_run=prepare), engine=engine, flow_id="FLOW",
                  expected_revision_id="frv_1", runtime_inputs=Inputs(), schedule=schedule)
    if outcome == "accepted":
        result = await accept_flow_run(**kwargs)
        assert result.model_dump() == {
            "flow_id": "FLOW", "revision_id": "frv_1", "session_id": "captured-session",
            "accepted_at": "2026-09-18T12:00:00+00:00",
            "summary": "Accepted through the bounded single-card flow run surface.",
        }
    elif outcome == "schedule_failure":
        with pytest.raises(RuntimeError, match="schedule refused"):
            await accept_flow_run(**kwargs)
    else:
        with pytest.raises(FlowRuntimeNotAdmittedError, match={
            "missing": "requires_assigned_card_present_on_host_card_surface",
            "unresolved": "requires_assigned_card_resolve_on_canonical_run_card_surface",
            "epic": "requires_assigned_card_resolve_to_issue_runtime_target",
        }[outcome]):
            await accept_flow_run(**kwargs)
    assert scheduled == ([(
        {"method_name": "run_issue", "args": ["CARD"], "kwargs": {"session_id": "captured-session"}},
        "run", "captured-session",
    )] if outcome in {"accepted", "schedule_failure"} else [])
