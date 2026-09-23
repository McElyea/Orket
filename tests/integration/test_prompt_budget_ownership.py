"""Layer: integration. Prompt-budget optional counters and artifacts retain admitted ownership."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.application.workflows import prompt_budget_guard as guard
from orket.application.workflows import prompt_token_counter as counters
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _policy() -> dict:
    limits = {key: 5000 for key in ("max_tokens", "protocol_tokens", "tool_schema_tokens", "task_tokens")}
    return {
        "schema_version": "1.0",
        "budget_policy_version": "1.0",
        "stages": {stage: dict(limits) for stage in ("planner", "executor", "reviewer")},
    }


def _write_policy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["schema_version: '1.0'", "budget_policy_version: '1.0'", "stages:"]
    for stage in ("planner", "executor", "reviewer"):
        rows.extend([f"  {stage}:", "    max_tokens: 5000", "    protocol_tokens: 5000",
                     "    tool_schema_tokens: 5000", "    task_tokens: 5000"])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


async def _thread_event(event: threading.Event) -> None:
    assert await asyncio.wait_for(asyncio.to_thread(event.wait, 1.0), 1.2)


def _destination(root: Path, *, turn_index: int = 1) -> TurnArtifactDestination:
    writer = TurnArtifactWriter(root)
    return TurnArtifactDestination(writer=writer, workspace=root.resolve(), session_id="session",
        issue_id="ISSUE-1", role_name="coder", role_id="role-1", turn_index=turn_index)


async def test_evaluation_captures_counter_inputs_before_policy_wait(monkeypatch, tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()
    selected_path = str(tmp_path / "selected.yaml")
    loaded_paths: list[str] = []

    def held_policy(path):  # type: ignore[no-untyped-def]
        loaded_paths.append(str(path))
        entered.set()
        assert release.wait(2)
        return _policy()

    provider_calls: list[list[dict]] = []
    direct_calls: list[list[dict]] = []

    class Provider:
        def count_tokens(self, messages):  # type: ignore[no-untyped-def]
            provider_calls.append(messages)
            return 99

    class Client:
        provider = Provider()

        def count_tokens(self, messages):  # type: ignore[no-untyped-def]
            direct_calls.append([dict(row) for row in messages])
            return {"token_count": len(messages), "tokenizer_id": "captured-counter"}

    monkeypatch.setattr(guard, "load_prompt_budget_policy", held_policy)
    messages = [{"role": "system", "content": "SYSTEM"},
                {"role": "user", "content": "Execution Context JSON:{}"},
                {"role": "user", "content": "Task"}]
    context = {"role": "coder", "prompt_budget_policy_path": selected_path,
               "prompt_budget_require_backend_tokenizer": True}
    client = Client()
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    task = asyncio.create_task(guard.evaluate_prompt_budget(messages=messages, context=context, model_client=client))
    try:
        await _thread_event(entered)
        messages[0]["content"] = "ROTATED"
        messages.append({"role": "user", "content": "late"})
        context.update(role="code_reviewer", prompt_budget_policy_path=str(tmp_path / "rotated.yaml"))
        client.count_tokens = client.provider.count_tokens  # type: ignore[method-assign]
        release.set()
        result = await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert loaded_paths == [selected_path] and result["stage"] == "executor"
    assert provider_calls == [] and [len(rows) for rows in direct_calls] == [3, 1, 1, 1]
    assert direct_calls[0][0]["content"] == "SYSTEM"


async def test_bucket_order_skips_empty_schema_and_keeps_payload_rules() -> None:
    calls: list[list[dict]] = []

    def count(messages):  # type: ignore[no-untyped-def]
        calls.append(messages)
        if len(calls) == 1:
            return {"token_count": 7, "tokenizer_id": "counter-v1"}
        if len(calls) == 2:
            return 2
        return {"prompt_tokens": 3}

    result = await counters.count_prompt_token_buckets(
        counter=count, known_async_counter=False,
        messages=[{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "Task"}],
        protocol_messages=[{"role": "system", "content": "SYSTEM"}], tool_schema_messages=[],
        task_messages=[{"role": "user", "content": "Task"}], require_backend_tokenizer=True,
    )
    assert [len(rows) for rows in calls] == [2, 1, 1]
    assert result == {"total_tokens": 7, "protocol_tokens": 2, "tool_schema_tokens": 0,
                      "task_tokens": 3, "tokenizer_id": "counter-v1", "tokenizer_source": "backend"}


async def test_sync_counter_drains_repeated_cancellation_without_later_bucket() -> None:
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    calls = 0

    def count(_messages):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(2)
        completed.set()
        return 1

    task = asyncio.create_task(counters.count_prompt_token_buckets(counter=count, known_async_counter=False,
        messages=[{"role": "user", "content": "Task"}], protocol_messages=[], tool_schema_messages=[],
        task_messages=[{"role": "user", "content": "Task"}], require_backend_tokenizer=True))
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    try:
        await _thread_event(entered)
        task.cancel()
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert completed.is_set() and calls == 1


async def test_sync_counter_returned_coroutine_drains_without_forwarded_cancel() -> None:
    entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    cancellations, calls = 0, 0

    async def continuation() -> int:
        nonlocal cancellations
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancellations += 1
            raise
        completed.set()
        return 1

    def count(_messages):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return continuation()

    task = asyncio.create_task(counters.count_prompt_token_buckets(counter=count, known_async_counter=False,
        messages=[{"role": "user", "content": "Task"}], protocol_messages=[], tool_schema_messages=[],
        task_messages=[{"role": "user", "content": "Task"}], require_backend_tokenizer=True))
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    try:
        await asyncio.wait_for(entered.wait(), .5)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert completed.is_set() and cancellations == 0 and calls == 1


async def test_known_async_counter_receives_one_cancel_and_no_later_bucket() -> None:
    entered, completed = asyncio.Event(), asyncio.Event()
    calls, cancellations = 0, 0

    class Counter:
        async def __call__(self, _messages):  # type: ignore[no-untyped-def]
            nonlocal calls, cancellations
            calls += 1
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellations += 1
                await asyncio.sleep(0)
                raise
            finally:
                completed.set()

    counter = Counter()
    task = asyncio.create_task(counters.count_prompt_token_buckets(counter=counter,
        known_async_counter=counters.is_known_async_counter(counter),
        messages=[{"role": "user", "content": "Task"}], protocol_messages=[], tool_schema_messages=[],
        task_messages=[{"role": "user", "content": "Task"}], require_backend_tokenizer=True))
    await asyncio.wait_for(entered.wait(), .5)
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert completed.is_set() and cancellations == 1 and calls == 1


@pytest.mark.parametrize("error_type,expected", [(ValueError, asyncio.CancelledError), (KeyError, KeyError)])
async def test_late_counter_failure_keeps_cancel_and_native_failure_precedence(error_type, expected) -> None:
    entered, release = threading.Event(), threading.Event()

    def count(_messages):  # type: ignore[no-untyped-def]
        entered.set()
        assert release.wait(2)
        raise error_type("late-counter")

    task = asyncio.create_task(counters._count_tokens(bucket="total", counter=count, known_async_counter=False,
        messages=[{"role": "user", "content": "Task"}], require_backend_tokenizer=True))
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    try:
        await _thread_event(entered)
        task.cancel()
        release.set()
        with pytest.raises(expected, match="late-counter" if expected is KeyError else None):
            await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("stage", ["policy", "artifact"])
async def test_policy_and_artifact_native_failure_stays_visible_after_cancel(
    monkeypatch, tmp_path: Path, stage,
) -> None:
    entered, release = threading.Event(), threading.Event()

    def fail_after_hold(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        entered.set()
        assert release.wait(2)
        raise OSError(f"{stage}-failed")

    destination = _destination(tmp_path)
    context = {"role": "coder", "prompt_budget_enabled": True,
               "prompt_budget_policy_path": str(tmp_path / "policy.yaml")}
    if stage == "policy":
        monkeypatch.setattr(guard, "load_prompt_budget_policy", fail_after_hold)
        operation = guard.evaluate_prompt_budget(messages=[{"role": "user", "content": "Task"}],
            context=context, model_client=object())
    else:
        monkeypatch.setattr(guard, "load_prompt_budget_policy", lambda _path: _policy())
        monkeypatch.setattr(guard, "write_prompt_budget_artifacts", fail_after_hold)
        operation = guard.maybe_record_prompt_budget(destination=destination, prompt_hash="hash",
            messages=[{"role": "user", "content": "Task"}], context=context, model_client=object())
    task = asyncio.create_task(operation)
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    try:
        await _thread_event(entered)
        task.cancel()
        release.set()
        with pytest.raises(OSError, match=f"{stage}-failed"):
            await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_held_counter_keeps_sqlite_responsive_and_publishes_captured_artifacts(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    await asyncio.to_thread(_write_policy, policy_path)
    destination = _destination(tmp_path, turn_index=2)
    previous = destination.output_dir_for_turn(1)
    await asyncio.to_thread(previous.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread((previous / "prompt_structure.json").write_text,
        json.dumps({"prompt_hash": "old"}), encoding="utf-8")
    entered, release = threading.Event(), threading.Event()
    calls: list[int] = []

    def count(messages):  # type: ignore[no-untyped-def]
        calls.append(len(messages))
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
        return {"token_count": len(messages), "tokenizer_id": "controlled-counter"}

    messages = [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "Task"}]
    context = {"role": "coder", "prompt_budget_enabled": True,
        "prompt_budget_require_backend_tokenizer": True, "prompt_budget_policy_path": str(policy_path),
        "prompt_metadata": {"prompt_version": "captured-v1"}}
    task = asyncio.create_task(guard.maybe_record_prompt_budget(destination=destination, prompt_hash="captured-hash",
        messages=messages, context=context, model_client=SimpleNamespace(count_tokens=count)))
    timer = asyncio.get_running_loop().call_later(1.5, release.set)
    try:
        await _thread_event(entered)
        messages.append({"role": "user", "content": "late"})
        context["prompt_metadata"]["prompt_version"] = "rotated"
        destination.writer.workspace = tmp_path / "rotated"
        started = perf_counter()
        async with aiosqlite.connect(tmp_path / "independent.sqlite3") as database:
            assert await (await database.execute("SELECT 1")).fetchone() == (1,)
        sqlite_seconds = perf_counter() - started
        release.set()
        result = await asyncio.wait_for(task, 2)
    finally:
        timer.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    usage_text = await asyncio.to_thread(
        destination.file_path("prompt_budget_usage.json").read_text, encoding="utf-8")
    usage = json.loads(usage_text)
    structure = json.loads(await asyncio.to_thread(destination.file_path("prompt_structure.json").read_text,
                                                    encoding="utf-8"))
    diff = await asyncio.to_thread(destination.file_path("prompt_diff.txt").read_text, encoding="utf-8")
    assert sqlite_seconds < .5 and result == usage and calls == [2, 1, 1]
    assert structure["message_count"] == 2 and structure["prompt_template_version"] == "captured-v1"
    assert structure["prompt_hash"] == "captured-hash" and "prompt_hash: 'old' -> 'captured-hash'" in diff
    assert not await asyncio.to_thread((tmp_path / "rotated").exists)
