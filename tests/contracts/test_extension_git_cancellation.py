"""Contract: incomplete Git interruption observations cannot become clean cancellation."""
from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.extensions.git_commands import ExtensionGitError, run_git

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("cleanup,capture,publication_failed", [
    (False, True, False), (True, False, False), (True, True, True),
])
async def test_git_interruption_preserves_uncertain_native_or_publication_failure(
    tmp_path: Path, monkeypatch, cleanup: bool, capture: bool, publication_failed: bool,
):
    observation = OwnedCommandResult(
        returncode=-1, stdout=b"private output", stderr=b"private diagnostics", reason="cancelled",
        cleanup_confirmed=cleanup, capture_complete=capture, backend="controlled",
        transport_pid=1, supervisor_pid=2, command_pid=3, diagnostics=(),
    )
    cancellation = CommandProcessCancelled(observation)
    if publication_failed:
        cancellation.__cause__ = OSError("cancellation record unavailable")

    async def interrupted(self, *args, **kwargs):
        raise cancellation

    monkeypatch.setattr(CommandProcessSupervisor, "run", interrupted)
    with pytest.raises(ExtensionGitError) as failure:
        await run_git(["status"], cwd=tmp_path, environment={})
    assert failure.value.observation is observation
    assert failure.value.__cause__ is cancellation
    assert "private" not in str(failure.value)
    assert ("E_EXT_GIT_CANCEL_RECORD_FAILED" if publication_failed else "E_EXT_GIT_INTERRUPTION_UNCERTAIN") in str(failure.value)
