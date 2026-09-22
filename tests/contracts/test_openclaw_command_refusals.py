"""Layer: contract. Synthetic observations prove refusal, not native process cleanup."""
from dataclasses import replace

import pytest

from orket.adapters.execution.openclaw_jsonl_adapter import OpenClawJsonlSubprocessAdapter
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("changes", [{"cleanup_confirmed": False}, {"capture_complete": False},
                                    {"reason": "cancelled"}, {"cleanup_confirmed": False, "reason": "launch_failed"}])
async def test_openclaw_refuses_uncertain_or_incomplete_lifetime(tmp_path, changes):
    result = replace(OwnedCommandResult(0, b'{"ok":true}\n', b"", "completed", True, True,
                                       "synthetic", 1, 2, 3, ()), **changes)

    class Runner:
        async def run_jsonl(self, *args, **kwargs):
            return result

    instance = OpenClawJsonlSubprocessAdapter(command=["fixture"], runner=Runner(), cwd=tmp_path)
    with pytest.raises(CommandExecutionUncertain) as failure:
        await instance.run_requests([{}])
    assert failure.value.lifetime is result


@pytest.mark.parametrize("frame", [b'{}\n{}\n', b'{}', bytearray(b'{}\n'), b'[]\n', b'\xff\n',
                                    pytest.param(b'{"deep":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}\n', id="deep-json")])
async def test_jsonl_request_refusal_precedes_command_admission(tmp_path, monkeypatch, frame):
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="unreachable")

    async def forbidden(*args, **kwargs):
        pytest.fail("invalid JSONL frame reached command admission")

    monkeypatch.setattr(owner, "run", forbidden)
    with pytest.raises(ValueError, match="E_COMMAND_JSONL_REQUEST"):
        await owner.run_jsonl(["fixture"], requests=[frame], cwd=tmp_path, io_timeout_seconds=1, environment={})


@pytest.mark.parametrize("budget", [float("nan"), float("inf"), -float("inf")])
async def test_openclaw_refuses_nonfinite_io_deadline(tmp_path, budget):
    with pytest.raises(ValueError, match="must be finite"):
        OpenClawJsonlSubprocessAdapter(command=["fixture"], runner=None, cwd=tmp_path, io_timeout_seconds=budget)
