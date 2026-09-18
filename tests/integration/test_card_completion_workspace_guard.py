"""Real file tools remain owned until their shared completion guard is released."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.tools.families.filesystem import FileSystemTools
from orket.adapters.tools.runtime import ToolRuntimeExecutor
from orket.application.services.card_workspace_mutation_service import CardWorkspaceMutationService
from orket.application.services.toolbox import ToolBox
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, completion_definition, write_completion_source

pytestmark = pytest.mark.integration


async def _ready(tmp_path):
    repo, service = completion_components(tmp_path / "cards.db", tmp_path / "workspace")
    await write_completion_source(service.workspace_root)
    await repo.save(IssueRecord(id="card", summary="Increment", seat="developer", status=CardStatus.CODE_REVIEW,
                                params={"completion_acceptance": completion_definition().model_dump(mode="json")}))
    context = await service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt")
    result = await service.evaluate_attempt(repo, context)
    return repo, service, result


@pytest.mark.asyncio
# Layer: integration
async def test_toolbox_write_cannot_cross_final_completion_writer_guard(tmp_path):
    repo, service, result = await _ready(tmp_path)
    toolbox = ToolBox(policy={}, workspace_root=str(service.workspace_root), references=[], cards_repo=repo, db_path=repo.db_path)
    async with repo.completion_write_guard():
        writing = asyncio.create_task(toolbox.execute("write_file", {"path": "agent_output/main.py", "content": "print('{}')\n"}))
        finished, _ = await asyncio.wait({writing}, timeout=0.1)
        assert not finished
    assert (await writing)["ok"]
    with pytest.raises(CardCompletionRejected, match="ACCEPTANCE_REQUIRED"):
        await repo.update_status("card", CardStatus.DONE, completion_request=result.request)
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW


@pytest.mark.asyncio
# Layer: integration
async def test_repeated_cancellation_drains_real_write_before_releasing_completion_guard(tmp_path):
    repo, service, result = await _ready(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    fs = FileSystemTools(service.workspace_root, [])

    async def delayed_write():
        started.set()
        await release.wait()
        return await fs.write_file({"path": "agent_output/main.py", "content": "print('{}')\n"})

    mutation = asyncio.create_task(CardWorkspaceMutationService(repo).run(delayed_write))
    await asyncio.wait_for(started.wait(), timeout=5)
    mutation.cancel()
    await asyncio.sleep(0)
    mutation.cancel()
    completion = asyncio.create_task(repo.update_status("card", CardStatus.DONE, completion_request=result.request))
    try:
        finished, _ = await asyncio.wait({mutation, completion}, timeout=0.1)
        assert not finished
    finally:
        release.set()
        observed = await asyncio.gather(mutation, completion, return_exceptions=True)
    assert isinstance(observed[0], asyncio.CancelledError)
    assert isinstance(observed[1], CardCompletionRejected)
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW
    assert (await fs.read_file({"path": "agent_output/main.py"}))["content"] == "print('{}')\n"
    assert await repo.get_card_history("card") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["timeout", "cancel", "timeout_then_cancel"])
# Layer: integration
async def test_sync_tool_write_retains_guard_until_thread_finishes(tmp_path, stop):
    repo, service, result = await _ready(tmp_path)
    started, release = asyncio.Event(), threading.Event()
    loop = asyncio.get_running_loop()
    destination = service.workspace_root / "agent_output" / "main.py"

    def delayed_write(args, context):
        loop.call_soon_threadsafe(started.set)
        if not release.wait(timeout=10):
            raise TimeoutError("Test did not release the file writer")
        destination.write_bytes(b"print('{}')\n")
        return {"ok": True}

    mutation = asyncio.create_task(ToolRuntimeExecutor().invoke(
        delayed_write, {}, workspace=service.workspace_root,
        tool_timeout_seconds=10 if stop == "cancel" else 0.05,
        mutation_authority=CardWorkspaceMutationService(repo),
    ))
    await asyncio.wait_for(started.wait(), timeout=5)
    if stop == "timeout_then_cancel":
        await asyncio.sleep(0.1)
    if stop != "timeout":
        mutation.cancel()
        await asyncio.sleep(0)
        mutation.cancel()
    completion = asyncio.create_task(repo.update_status("card", CardStatus.DONE, completion_request=result.request))
    try:
        finished, _ = await asyncio.wait({mutation, completion}, timeout=0.15)
        assert not finished
    finally:
        release.set()
        observed = await asyncio.gather(mutation, completion, return_exceptions=True)
    if stop == "timeout":
        assert observed[0]["error"] == "tool_timeout"
    else:
        assert isinstance(observed[0], asyncio.CancelledError)
    assert isinstance(observed[1], CardCompletionRejected)
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW
    assert await asyncio.to_thread(destination.read_bytes) == b"print('{}')\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [False, True], ids=["default", "selected"])
# Layer: integration
async def test_builtin_sync_writer_uses_completion_guard_under_selected_strategy(tmp_path, selected):
    workspace = tmp_path / "project" / "workspace" / "active"
    source = workspace.parent / "runs" / "seed"
    await asyncio.to_thread(source.mkdir, parents=True)
    await asyncio.to_thread((source / "result.txt").write_bytes, b"retained result")
    repo, _ = completion_components(tmp_path / "cards.db", workspace)
    toolbox = ToolBox(None, str(workspace), [], db_path=repo.db_path, cards_repo=repo)
    if selected:
        toolbox.tool_strategy_node = SimpleNamespace(select_tools=lambda inputs: ("archive_eval",))
    async with repo.completion_write_guard():
        writing = asyncio.create_task(toolbox.execute("archive_eval", {"session_id": "seed", "label": "guard"}))
        finished, _ = await asyncio.wait({writing}, timeout=0.1)
        assert not finished
        assert not await asyncio.to_thread((workspace.parent.parent / "evals").exists)
    result = await writing
    assert result["ok"] is True
    assert await asyncio.to_thread((Path(result["path"]) / "result.txt").read_bytes) == b"retained result"
