"""Layer: integration. Controlled native receipts, actual SQLite reconciliation state."""
from __future__ import annotations

from dataclasses import replace

import pytest

from orket.adapters.storage.command_runner import CommandRunner, SandboxCommandTimeout, SandboxCommandUncertain
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.core.domain.sandbox_lifecycle import SandboxState
from tests.integration.test_sandbox_deploy_publication_recovery import _create, _owner

pytestmark = pytest.mark.asyncio
COMPLETED = OwnedCommandResult(0, b"", b"", "completed", True, True, "windows_job", 1, 2, 3, ())


class ControlledReceipt:
    def __init__(self, receipt):
        self.receipt = receipt

    async def run(self, *args, **kwargs):
        return self.receipt


@pytest.mark.parametrize("changes,exception", [
    ({"cleanup_confirmed": False}, SandboxCommandUncertain),
    ({"capture_complete": False}, SandboxCommandUncertain),
    ({"returncode": None}, SandboxCommandUncertain),
    ({"returncode": True}, SandboxCommandUncertain),
    ({"reason": "output_limit", "capture_complete": False}, SandboxCommandUncertain),
    ({"reason": "launch_failed", "capture_complete": False, "command_pid": None}, SandboxCommandUncertain),
    ({"reason": "timeout"}, SandboxCommandTimeout),
])
@pytest.mark.integration
async def test_incomplete_deployment_keeps_reconciliation_and_no_terminal_receipt(tmp_path, changes, exception):
    owner = _owner(tmp_path)
    observed = replace(COMPLETED, **changes)
    owner.command_runner = CommandRunner(owner=ControlledReceipt(observed), cwd=tmp_path,
                                         environment={}, timeout_seconds=10)
    with pytest.raises(exception) as caught:
        await _create(owner, tmp_path)
    assert caught.value.lifetime == observed
    record = await owner.lifecycle_repository.get_record("sandbox-rock-1")
    assert record.state is SandboxState.STARTING
    assert record.requires_reconciliation is True
    assert record.terminal_reason is None
    assert await owner.control_plane_repository.list_effect_journal_entries(run_id="rock-1") == []


@pytest.mark.contract
async def test_custom_owner_environment_mutation_does_not_change_next_invocation(tmp_path):
    observations = []

    class MutatingPort:
        async def run(self, argv, **kwargs):
            observations.append((argv, dict(kwargs["environment"])))
            kwargs["environment"]["VALUE"] = "owner-mutated"
            return COMPLETED

    environment = {"VALUE": "admitted"}
    runner = CommandRunner(owner=MutatingPort(), cwd=tmp_path, environment=environment, timeout_seconds=10)
    environment["VALUE"] = "caller-mutated"
    assert (await runner.run_async("first")).returncode == 0
    assert (await runner.run_async("second")).returncode == 0
    assert observations == [(("first",), {"VALUE": "admitted"}), (("second",), {"VALUE": "admitted"})]
