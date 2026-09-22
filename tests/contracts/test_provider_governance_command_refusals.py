"""Layer: contract. Controlled supervisor results exercise refusal, not native cleanup proof."""
import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult
from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config.provider_runtime_target import _owned_inventory
from scripts.governance import record_truthful_runtime_packet1_live_proof as packet1

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("route", ["inventory", "packet1"])
@pytest.mark.parametrize("reason,cleanup,capture", [
    ("cleanup_unconfirmed", False, False), ("capture_incomplete", True, False),
    ("completed", True, False), ("cancelled", True, True),
    ("launch_failed", False, False), ("output_limit", True, False),
])
async def test_incomplete_command_cannot_return_normal_output(tmp_path, monkeypatch, route, reason, cleanup, capture):
    monkeypatch.chdir(tmp_path)
    declared = OwnedCommandResult(0, b"success-shaped partial data", b"", reason, cleanup, capture,
                                  "unavailable", 1, 2, 3, ("controlled protocol result",))

    async def simulated(_owner, *_args, **_kwargs):
        return declared

    monkeypatch.setattr(CommandProcessSupervisor, "run", simulated)
    with pytest.raises(CommandExecutionUncertain) as observed:
        if route == "inventory":
            await _owned_inventory(inventory._run_command_sync, cmd=["controlled-command"], timeout_s=5)
        else:
            await packet1._run_command("controlled-command")
    assert observed.value.lifetime is declared
