# Layer: integration
from __future__ import annotations

from copy import deepcopy

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_context_plan import validate_continuation_inputs
from orket.application.services.governed_agent_wake_ingress_service import GovernedAgentWakeSubmission
from orket_extension_sdk import AgentIterationRequest
from tests.runtime.governed_agent_test_support import staged_agent_request, ticket_continuation_inputs

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_future_context_survives_restart_without_entering_initial_request(tmp_path):
    """Layer: integration. Durable ingress retains future inputs outside the child request."""
    request = staged_agent_request()
    plan = ticket_continuation_inputs()
    payload = {
        "occurrence_id": "staged-report", "target_kind": "new_run", "workload_id": "governed-agent-loop",
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1", "request": request,
            "creation_timestamp_utc": "2026-09-09T00:00:00Z",
            "decision_timestamps_utc": ["2026-09-09T00:00:01Z", "2026-09-09T00:00:02Z"],
            "next_lease_expiries_utc": [request["lease_expires_at_utc"]], "continuation_inputs": plan,
        },
    }
    submission = GovernedAgentWakeSubmission.from_mapping(payload)
    db = tmp_path / "context.sqlite3"
    wake_request = submission.to_request(source="api", created_at_utc="2026-09-09T00:00:00Z")
    created = await AsyncGovernedAgentWakeRepository(db).enqueue(wake_request)
    restored = await AsyncGovernedAgentWakeRepository(db).get_wake(wake_id=created.wake.wake_id)
    assert restored.payload["continuation_inputs"] == plan
    assert restored.payload["request"] == request
    assert request["authoritative_context_refs"] == ["artifact:ticket-batch-a"]
    changed = deepcopy(payload)
    changed["dispatch"]["continuation_inputs"] = {}
    conflicting = GovernedAgentWakeSubmission.from_mapping(changed).to_request(
        source="api", created_at_utc="2026-09-09T00:00:00Z",
    )
    assert (await AsyncGovernedAgentWakeRepository(db).enqueue(conflicting)).status == "conflict"


@pytest.mark.parametrize("mutation, error", [
    ("digest", "DIGEST"), ("kind", "KIND"), ("duplicate", "SCHEMA"),
    ("ordinal", "ORDINAL"), ("budget", "EXCEEDS_RUN_BUDGET"),
])
def test_future_context_fails_closed(mutation, error):
    """Layer: contract. Future context uses the same materialization validation as dispatched input."""
    request = AgentIterationRequest.from_wire(staged_agent_request())
    plan = ticket_continuation_inputs()
    if mutation == "digest":
        plan["2"][0]["digest"] = "sha256:" + "0" * 64
    elif mutation == "kind":
        plan["2"][0]["kind"] = "objective"
    elif mutation == "duplicate":
        plan["2"].append(deepcopy(plan["2"][0]))
    else:
        plan["02" if mutation == "ordinal" else "3"] = plan.pop("2")
    with pytest.raises(ValueError, match=error):
        validate_continuation_inputs(request, plan)
