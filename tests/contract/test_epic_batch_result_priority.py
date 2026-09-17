"""Batch exception priority preserves unresolved effects across parallel cards."""
import asyncio

import pytest

from orket.application.services.epic_dispatch_batch import run_epic_dispatch_batch
from orket.application.services.fixture_verification_service import FixtureVerificationUncertain
from orket.exceptions import ApprovalPending, ExecutionFailed

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("reverse", [False, True])
# Layer: contract
async def test_uncertain_cleanup_is_not_hidden_by_business_failure(reverse):
    uncertainty = FixtureVerificationUncertain({"cleanup_confirmed": False})
    failures = [ExecutionFailed("business failure"), uncertainty, ApprovalPending("approval wait")]
    drained = []

    async def dispatch(error):
        await asyncio.sleep(0)
        drained.append(error)
        raise error

    with pytest.raises(FixtureVerificationUncertain) as observed:
        await run_epic_dispatch_batch(failures[::-1] if reverse else failures, dispatch)
    assert observed.value is uncertainty
    assert len(drained) == len(failures)


# Layer: contract
async def test_cancelled_child_keeps_cancellation_semantics_after_siblings_finish():
    cancelled = asyncio.CancelledError("child cancelled")
    completed = []

    async def dispatch(error):
        await asyncio.sleep(0)
        completed.append(error)
        raise error

    with pytest.raises(asyncio.CancelledError):
        await run_epic_dispatch_batch([ExecutionFailed("business"), RuntimeError("uncertain"), cancelled], dispatch)
    assert len(completed) == 3
