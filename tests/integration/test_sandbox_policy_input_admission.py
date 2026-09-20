"""Real SQLite admission and retained lifecycle truth; Docker acceptance is separate."""
import asyncio

import pytest
from pydantic import ValidationError

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.decision_nodes.builtins import DefaultSandboxPolicyNode
from tests.integration.test_sandbox_creation_capture import _create, _owner

pytestmark = pytest.mark.integration


class CapturedSecrets(RuntimeInputService):
    def __init__(self):
        self.calls = []
        self.suffix = "admitted"

    def create_secret_token(self):
        self.calls.append(self.suffix)
        return f"synthetic-{self.suffix}-{len(self.calls)}"


@pytest.mark.asyncio
async def test_database_policy_cannot_mutate_ports_and_refusal_releases_its_allocation(tmp_path):
    class Mutation(DefaultSandboxPolicyNode):
        def get_database_url(self, tech_stack, ports, db_password=""):
            ports.api = 9999
    owner = _owner(tmp_path, CapturedSecrets())
    owner.registry.port_allocator.allocated_ports["other"] = 42
    owner.sandbox_policy_node = Mutation()
    with pytest.raises(ValidationError, match="frozen_instance"):
        await _create(owner, tmp_path)
    assert owner.registry.port_allocator.allocated_ports == {"other": 42}
    assert owner.registry.port_allocator.next_available_base == 2
    assert owner.registry.sandboxes == {}
    assert await owner.lifecycle_repository.get_record("sandbox-captured") is None
    assert not (tmp_path/"control_plane_records.sqlite3").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["build_compose_project", "get_database_url"])
async def test_bad_policy_text_releases_allocation_without_durable_reservation(tmp_path, method):
    owner = _owner(tmp_path, CapturedSecrets())
    node = DefaultSandboxPolicyNode()
    setattr(node, method, lambda *args: {"not": "text"})
    owner.sandbox_policy_node = node
    with pytest.raises(ValueError, match="E_SANDBOX_POLICY_INVALID"):
        await _create(owner, tmp_path)
    assert owner.registry.port_allocator.allocated_ports == {} and owner.registry.sandboxes == {}
    assert not (tmp_path/"control_plane_records.sqlite3").exists()


@pytest.mark.asyncio
async def test_selected_policy_and_secrets_are_captured_before_actual_preflight(tmp_path, monkeypatch):
    inputs = CapturedSecrets()
    owner = _owner(tmp_path, inputs)
    observed = []
    class Observer(DefaultSandboxPolicyNode):
        def __init__(self, name):
            self.name = name
        def get_database_url(self, tech_stack, ports, db_password=""):
            observed.append((self.name, tech_stack, db_password))
            raise ValueError("controlled policy refusal")
    owner.sandbox_policy_node = Observer("admitted")
    entered, release = asyncio.Event(), asyncio.Event()
    read = owner.lifecycle_service.repository.get_record
    async def held(sandbox_id):
        result = await read(sandbox_id)
        entered.set()
        await release.wait()
        return result
    monkeypatch.setattr(owner.lifecycle_service.repository, "get_record", held)
    operation = asyncio.create_task(_create(owner, tmp_path))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert inputs.calls == ["admitted", "admitted"]
        inputs.suffix = "replacement"
        owner.sandbox_policy_node = Observer("replacement")
        release.set()
        with pytest.raises(ValueError, match="controlled policy refusal"):
            await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert observed == [("admitted", "fastapi-react-postgres", "synthetic-admitted-1")]
    assert inputs.calls == ["admitted", "admitted"]
    assert owner.registry.port_allocator.allocated_ports == {}


@pytest.mark.asyncio
async def test_compose_refusal_preserves_durable_reconciliation_state_without_docker(tmp_path):
    calls = []
    class Mutation(DefaultSandboxPolicyNode):
        def generate_compose_file(self, sandbox, db_password, admin_password):
            calls.append((db_password, admin_password))
            sandbox.ports.api = 9999
    owner = _owner(tmp_path, CapturedSecrets())
    owner.sandbox_policy_node = Mutation()
    with pytest.raises(ValidationError, match="frozen_instance"):
        await _create(owner, tmp_path)
    assert calls == [("synthetic-admitted-1", "synthetic-admitted-2")]
    sandbox = owner.registry.get("sandbox-captured")
    assert sandbox.ports.api == 8001 and sandbox.rock_id == "captured"
    record = await owner.lifecycle_repository.get_record(sandbox.id)
    assert record.state.value == "starting" and record.requires_reconciliation is True
    assert not owner._compose_path(tmp_path).exists()
    effects = await owner.control_plane_repository.list_effect_journal_entries(run_id="captured")
    assert effects == []


@pytest.mark.asyncio
async def test_compose_uses_admitted_policy_and_secrets_after_publication_await(tmp_path, monkeypatch):
    inputs = CapturedSecrets()
    owner = _owner(tmp_path, inputs)
    observed = []
    class Observer(DefaultSandboxPolicyNode):
        def __init__(self, name):
            self.name = name
        def generate_compose_file(self, sandbox, db_password, admin_password):
            observed.append((self.name, sandbox.id, db_password, admin_password))
            raise ValueError("controlled compose refusal")
    owner.sandbox_policy_node = Observer("admitted")
    entered, release = asyncio.Event(), asyncio.Event()
    publish = owner.control_plane_reservations.publish_allocation_reservation
    async def held(**kwargs):
        result = await publish(**kwargs)
        entered.set()
        await release.wait()
        return result
    monkeypatch.setattr(owner.control_plane_reservations, "publish_allocation_reservation", held)
    operation = asyncio.create_task(_create(owner, tmp_path))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        owner.sandbox_policy_node = Observer("replacement")
        inputs.suffix = "replacement"
        release.set()
        with pytest.raises(ValueError, match="controlled compose refusal"):
            await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert observed == [("admitted", "sandbox-captured", "synthetic-admitted-1", "synthetic-admitted-2")]
    assert inputs.calls == ["admitted", "admitted"]
    record = await owner.lifecycle_repository.get_record("sandbox-captured")
    assert record.state.value == "starting" and record.requires_reconciliation is True
