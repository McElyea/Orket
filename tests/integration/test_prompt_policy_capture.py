"""Layer: integration. Relative prompt policy admission binds one physical root."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from orket.application.workflows import prompt_budget_guard as guard
from orket.runtime.config import contract_assets
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_relative_policy_root_survives_cwd_change(tmp_path, monkeypatch, record_property):
    first, second = tmp_path / "first", tmp_path / "second"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(second.mkdir)
    source = await asyncio.to_thread(contract_assets.DEFAULT_PROMPT_BUDGET_PATH.read_bytes)
    await asyncio.to_thread((first / "budget.yaml").write_bytes, source)
    await asyncio.to_thread((second / "budget.yaml").write_text, "invalid: other-root", encoding="utf-8")
    entered, release = threading.Event(), threading.Event()
    selected = []
    original = guard.load_prompt_budget_policy

    def held(path):
        selected.append(Path(path))
        entered.set()
        assert release.wait(5), "policy read not released"
        return original(path)

    monkeypatch.chdir(first)
    monkeypatch.setattr(guard, "load_prompt_budget_policy", held)
    task = asyncio.create_task(guard.evaluate_prompt_budget(
        messages=[{"role": "user", "content": "Task"}],
        context={"prompt_budget_policy_path": "budget.yaml"}, model_client=object(),
    ))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.chdir(second)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 5)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)

    assert selected == [first / "budget.yaml"]
    assert result["ok"] is True
    assert result["tokenizer_source"] == "deterministic_fallback"
    record_property("captured_policy_path", str(selected[0]))
