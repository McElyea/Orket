"""Integration: an admitted filesystem mutation retains its real completion guard."""
import asyncio

import pytest

from orket.adapters.tools.families.filesystem import FileSystemTools
from orket.application.services.card_workspace_mutation_service import CardWorkspaceMutationService
from tests.integration.test_async_file_invocation_inputs import hold_path_method
from tests.integration.test_card_completion_workspace_guard import _ready

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("operation", ["write_file", "create_directory"])
async def test_file_mutation_retains_authority_while_resolving_path(tmp_path, monkeypatch, operation):
    repo, service, _ = await _ready(tmp_path)
    tools = FileSystemTools(service.workspace_root, [], mutation_authority=CardWorkspaceMutationService(repo))
    relative = "agent_output/main.py" if operation == "write_file" else "admitted-directory"
    target = service.workspace_root / relative
    original = await asyncio.to_thread(target.read_bytes) if operation == "write_file" else None
    state = hold_path_method(monkeypatch, "resolve", target)
    args = {"path": relative, "content": "admitted replacement"}
    task = None
    try:
        async with repo.completion_write_guard():
            task = asyncio.create_task(getattr(tools, operation)(args))
            assert await asyncio.to_thread(state.entered.wait, 5)
            assert not state.finished.is_set()
            tools.mutation_authority = None
            state.release.set()
            finished, _ = await asyncio.wait({task}, timeout=.1)
            assert not finished, "A changed attribute bypassed the admitted completion guard"
            if operation == "write_file":
                assert await asyncio.to_thread(target.read_bytes) == original
            else:
                assert not await asyncio.to_thread(target.exists)
        assert (await asyncio.wait_for(task, 5))["ok"] is True
    finally:
        state.release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)
