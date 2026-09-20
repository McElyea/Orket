"""Real SQLite preflight with controlled publication refusal; Docker proof is separate."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.sandbox import TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class ObservedInputs(RuntimeInputService):
    def __init__(self):
        self.value = datetime.now(UTC).replace(microsecond=123456)
        self.calls = 0
        self.failure = None

    def utc_now(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.value


def _owner(tmp_path, inputs):
    return SandboxOrchestrator(workspace_root=tmp_path, runtime_inputs=inputs,
                               lifecycle_db_path=str(tmp_path / 'sandbox.sqlite3'))


def _create(owner, tmp_path):
    return owner.create_sandbox(rock_id='captured', project_name='Captured',
                                tech_stack=TechStack.FASTAPI_REACT_POSTGRES, workspace_path=str(tmp_path))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_creation_time_is_captured_before_real_preflight_suspends(tmp_path, monkeypatch):
    inputs = ObservedInputs()
    admitted = inputs.value.isoformat()
    owner = _owner(tmp_path, inputs)
    original = owner.lifecycle_service.repository.get_record
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    async def held_read(sandbox_id):
        value = await original(sandbox_id)
        entered.set()
        await release.wait()
        return value

    async def refuse_publication(**kwargs):
        seen.append(kwargs['creation_timestamp'])
        raise ValueError('controlled publication refusal')

    monkeypatch.setattr(owner.lifecycle_service.repository, 'get_record', held_read)
    monkeypatch.setattr(owner.control_plane_reservations, 'publish_allocation_reservation', refuse_publication)
    task = asyncio.create_task(_create(owner, tmp_path))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert inputs.calls == 1
        inputs.value += timedelta(days=1)
    finally:
        release.set()
        with pytest.raises(ValueError, match='controlled publication refusal'):
            await task
    assert seen == [admitted]
    assert inputs.calls == 1
    assert owner.registry.port_allocator.allocated_ports == {}
    assert owner.registry.sandboxes == {}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clock_failure_precedes_repository_and_port_allocation(tmp_path, monkeypatch):
    inputs = ObservedInputs()
    inputs.failure = OSError('clock unavailable')
    owner = _owner(tmp_path, inputs)

    async def forbidden_read(_sandbox_id):
        pytest.fail('repository was reached after clock failure')

    monkeypatch.setattr(owner.lifecycle_service.repository, 'get_record', forbidden_read)
    with pytest.raises(OSError, match='clock unavailable'):
        await _create(owner, tmp_path)
    assert inputs.calls == 1
    assert owner.registry.port_allocator.allocated_ports == {}
    assert owner.registry.port_allocator.next_available_base == 1
    assert not (tmp_path / 'sandbox.sqlite3').exists()


@pytest.mark.contract
def test_existing_lifecycle_observations_keep_second_precision(tmp_path):
    inputs = ObservedInputs()
    owner = _owner(tmp_path, inputs)
    assert owner._now() == inputs.value.replace(microsecond=0).isoformat()
    assert inputs.calls == 1
