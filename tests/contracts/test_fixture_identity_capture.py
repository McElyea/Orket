"""Layer: contract. declared container port, not live Docker proof."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orket.application.services import fixture_verification_service as service_module
from tests.helpers.fixture_input_controls import prepare_native, selected_time
from tests.helpers.runtime_verification_hold import hold_path, settle, wait_entered

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]
OWNER_ID = "67afec3b-d21e-4c37-8b80-4eb591826f91"


async def test_fixture_binds_existing_identity_provider_before_metadata(tmp_path, monkeypatch):
    verification = await asyncio.to_thread(prepare_native, tmp_path)
    calls, admitted = [], []

    def create_identity():
        calls.append(OWNER_ID)
        return OWNER_ID

    class DeclaredOwner:
        def __init__(self, **values):
            admitted.append(values)

        async def run(self, **_values):
            raise OSError("controlled owner refusal; no actual container")

    provider = SimpleNamespace(create_effect_owner_id=create_identity)
    service = service_module.FixtureVerificationService(tmp_path, utc_now=selected_time,
        runtime_inputs=provider, environment={"ORKET_VERIFY_EXECUTION_MODE": "container"})
    monkeypatch.setattr(service_module, "FixtureContainerOwner", DeclaredOwner)
    hold = hold_path(monkeypatch, "is_file", tmp_path / "verification/fixture.py")
    task = asyncio.create_task(service.verify(verification))
    try:
        await wait_entered(hold)
        provider.create_effect_owner_id = lambda: pytest.fail("replacement identity provider selected")
        service.runtime_inputs = SimpleNamespace(create_effect_owner_id=lambda: pytest.fail("replacement provider selected"))
        hold.release.set()
        result = await task
        assert calls == [OWNER_ID] and admitted[0]["owner_id"] == OWNER_ID
        assert admitted[0]["name"] == "orket-verification-" + OWNER_ID.replace("-", "")
        assert result.failed == 1 and result.process_lifetime is None
    finally:
        await settle(task, hold)
