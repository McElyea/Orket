"""Layer: integration. Stored-turn reentry must not mint historical timestamps."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import aiofiles
import pytest

from orket.agents.agent import Agent
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("deterministic_turn_clock")]


def artifact_snapshot(root: Path) -> dict:
    """Read-only observation performed in a worker."""
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}


class FileToolbox:
    def __init__(self, root: Path) -> None:
        self.root, self.calls = root, 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        path = self.root / args["path"]
        async with aiofiles.open(path, "w", encoding="utf-8") as output:
            await output.write(args["content"])
        async with aiofiles.open(path, encoding="utf-8") as output:
            assert await output.read() == args["content"]
        return {"ok": True, "tool": tool_name, "touched_paths": [args["path"]]}


@pytest.mark.asyncio
async def test_completed_reentry_does_not_invent_a_turn_timestamp(tmp_path: Path) -> None:
    await asyncio.to_thread((tmp_path / "agent_output").mkdir)
    service = build_turn_tool_control_plane_service(tmp_path / "control.sqlite3")
    executor = TurnExecutor(StateMachine(), ToolGate(None, tmp_path), tmp_path, control_plane_service=service, utc_now=artifact_test_utc_now)
    model, toolbox = _Model(), FileToolbox(tmp_path)
    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert first.success and first.turn.timestamp is not None
    artifact_bytes = await asyncio.to_thread(artifact_snapshot, tmp_path)
    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    third = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    assert second.success and third.success
    assert second.turn.note == third.turn.note == "control_plane_completed_replay"
    assert model.calls == toolbox.calls == 1
    async with aiofiles.open(tmp_path / "agent_output/out.txt", encoding="utf-8") as output:
        assert await output.read() == "ok"
    assert artifact_bytes == await asyncio.to_thread(artifact_snapshot, tmp_path)
    # Existing checkpoint snapshots do not record the original response time.
    assert second.turn.timestamp is None and third.turn.timestamp is None


class TextProvider:
    model = "clock-fixture"

    async def complete(self, messages):
        assert messages
        return SimpleNamespace(content="Observed response.", raw={"total_tokens": 2})


@pytest.mark.asyncio
async def test_agent_uses_the_supplied_turn_clock(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 18, 12, 30, tzinfo=UTC)
    calls = []

    def clock():
        calls.append(observed)
        return observed

    # Deliberately exercise documented missing-config degradation with real files.
    # The provider supplies a controlled response; this is not live model proof.
    agent = Agent("clock-fixture", "Read a response", {}, TextProvider(), config_root=tmp_path,
                  strict_config=False, turn_clock=clock)
    turn = await agent.run({"description": "Observe"}, {"issue_id": "CLOCK-1"}, tmp_path)
    assert turn.timestamp == observed
    assert calls == [observed]
    assert turn.content == "Observed response." and turn.tokens_used == 2


@pytest.mark.asyncio
async def test_agent_captures_clock_selection_before_provider_wait(tmp_path: Path) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    observed = datetime(2026, 9, 18, 12, 30, tzinfo=UTC)

    class HeldProvider(TextProvider):
        async def complete(self, messages):
            entered.set()
            await release.wait()
            return await super().complete(messages)

    agent = Agent("clock-fixture", "Read a response", {}, HeldProvider(), config_root=tmp_path,
                  strict_config=False, turn_clock=lambda: observed)
    task = asyncio.create_task(agent.run({"description": "Observe"}, {"issue_id": "CLOCK-2"}, tmp_path))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        agent.turn_clock = lambda: datetime.max.replace(tzinfo=UTC)
    finally:
        release.set()
        turn = await task
    assert turn.timestamp == observed
