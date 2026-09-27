"""Opening proof for llama template-read ownership and cancellation settlement."""
from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import httpx
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.llm import llama_cpp_render_verification as render_module
from tests.helpers.gitea_loop_inputs import assert_sqlite_response, probe_database

_TEMPLATE_BYTES = b"fixture-template-bytes\n"
_PAYLOAD = {
    "model": "fixture-model",
    "messages": [{"role": "user", "content": "fixture prompt"}],
    "max_tokens": 1,
}


@dataclass
class _ReadGate:
    target: Path
    original: Callable[[Path], bytes]
    loop: asyncio.AbstractEventLoop
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    release: threading.Event = field(default_factory=threading.Event)
    calls: int = 0
    worker_thread_id: int | None = None
    error: OSError | None = None

    def read(self, path: Path) -> bytes:
        if path != self.target:
            return self.original(path)
        self.calls += 1
        self.worker_thread_id = threading.get_ident()
        self.loop.call_soon_threadsafe(self.entered.set)
        self.release.wait()
        try:
            return self.original(path)
        except OSError as exc:
            self.error = exc
            raise
        finally:
            self.loop.call_soon_threadsafe(self.finished.set)


@dataclass
class _Case:
    template: Path
    gate: _ReadGate
    task: asyncio.Task[dict[str, object]]
    client: httpx.AsyncClient
    requests: list[str]
    caller_thread_id: int


def _forbidden_http_client(requests: list[str]) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.method} {request.url}")
        raise AssertionError("HTTP was admitted after template-read cancellation")

    return httpx.AsyncClient(
        base_url="http://llama.invalid/v1",
        transport=httpx.MockTransport(handle),
    )


async def _open_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Case:
    template = tmp_path / "template.jinja"
    await run_owned_thread(
        partial(template.write_bytes, _TEMPLATE_BYTES),
        label="llama-template-fixture-write",
    )
    loop = asyncio.get_running_loop()
    path_type = type(template)
    gate = _ReadGate(target=template, original=path_type.read_bytes, loop=loop)

    def controlled_read(path: Path) -> bytes:
        return gate.read(path)

    monkeypatch.setattr(path_type, "read_bytes", controlled_read)
    monkeypatch.setattr(render_module, "QWEN38_TEXT_TEMPLATE_PATH", template)
    requests: list[str] = []
    client = _forbidden_http_client(requests)
    task = asyncio.create_task(
        render_module.verify_llama_cpp_render(
            client=client,
            headers={},
            payload=_PAYLOAD,
            template_version=render_module.QWEN38_TEXT_TEMPLATE_VERSION,
            context_budget_tokens=64,
        )
    )
    try:
        await asyncio.wait_for(gate.entered.wait(), 5)
    except (TimeoutError, asyncio.CancelledError):
        gate.release.set()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()
        raise
    return _Case(template, gate, task, client, requests, threading.get_ident())


async def _cancel_while_held(case: _Case, count: int) -> tuple[list[bool], bool]:
    requests = []
    loop = asyncio.get_running_loop()
    for _ in range(count):
        requests.append(case.task.cancel())
        turn_completed = asyncio.Event()
        loop.call_soon(turn_completed.set)
        await turn_completed.wait()
    return requests, case.task.done()


async def _release_and_join(case: _Case) -> BaseException | dict[str, object]:
    case.gate.release.set()
    try:
        await asyncio.wait_for(case.gate.finished.wait(), 5)
        result, = await asyncio.gather(case.task, return_exceptions=True)
        return result
    finally:
        case.gate.release.set()
        if not case.task.done():
            case.task.cancel()
        await asyncio.gather(case.task, return_exceptions=True)
        await case.client.aclose()


def _initial_observation(case_id: str, cancel_count: int) -> dict[str, object]:
    return {
        "schema_version": "llama_template_ownership_observation.v2",
        "case_id": case_id,
        "stage": "setup_not_started",
        "target_ready": False,
        "admission_reached": False,
        "sqlite_control_passed": False,
        "file_removed": False,
        "cancel_count": cancel_count,
        "cancellation_returns": None,
        "cancellation_return_count": 0,
        "held_task_done": None,
        "cleanup_returned": False,
        "physical_finished": None,
        "read_count": None,
        "worker_thread_id": None,
        "caller_thread_id": None,
        "thread_separated": None,
        "native_error_type": None,
        "outcome_type": "unavailable",
        "outward_is_native_error": None,
        "http_requests": None,
        "http_request_count": None,
        "task_done_after_cleanup": None,
        "client_closed": None,
    }


def _capture_case(
    observation: dict[str, object], case: _Case | None,
    outcome: BaseException | dict[str, object] | None,
) -> None:
    if case is None:
        return
    gate = case.gate
    observation.update(
        physical_finished=gate.finished.is_set(),
        read_count=gate.calls,
        worker_thread_id=gate.worker_thread_id,
        caller_thread_id=case.caller_thread_id,
        thread_separated=(
            gate.worker_thread_id is not None
            and gate.worker_thread_id != case.caller_thread_id
        ),
        native_error_type=None if gate.error is None else type(gate.error).__name__,
        outcome_type="unavailable" if outcome is None else type(outcome).__name__,
        outward_is_native_error=(
            None if gate.error is None or outcome is None else outcome is gate.error
        ),
        http_requests=list(case.requests),
        http_request_count=len(case.requests),
        task_done_after_cleanup=case.task.done(),
        client_closed=case.client.is_closed,
    )


async def _settle_and_record(
    case: _Case | None,
    observation: dict[str, object],
    record_property,
) -> BaseException | dict[str, object] | None:
    outcome: BaseException | dict[str, object] | None = None
    try:
        if case is not None:
            outcome = await _release_and_join(case)
            observation["cleanup_returned"] = True
            observation["stage"] = (
                "complete_before_target_assertion"
                if observation["target_ready"] is True
                else "cleanup_complete_without_target_ready"
            )
        return outcome
    finally:
        _capture_case(observation, case, outcome)
        record_property(
            "llama_template_ownership_observation",
            json.dumps(observation, sort_keys=True),
        )


@pytest.mark.parametrize("cancel_count", [1, 3], ids=["single", "repeated"])
@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Real Path.read_bytes worker, cancellation settlement, and loop response.
async def test_cancelled_template_read_settles_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property,
    cancel_count: int,
) -> None:
    case: _Case | None = None
    observation = _initial_observation("successful_read", cancel_count)
    try:
        database = await probe_database(tmp_path)
        observation["stage"] = "database_ready"
        case = await _open_case(tmp_path, monkeypatch)
        observation.update(stage="admission_reached", admission_reached=True)
        await assert_sqlite_response(database, record_property)
        observation.update(stage="sqlite_control_passed", sqlite_control_passed=True)
        cancel_requests, settled_while_held = await _cancel_while_held(case, cancel_count)
        observation.update(
            stage="cancellation_observed",
            target_ready=True,
            cancellation_returns=cancel_requests,
            cancellation_return_count=len(cancel_requests),
            held_task_done=settled_while_held,
        )
    finally:
        outcome = await _settle_and_record(case, observation, record_property)

    assert observation["stage"] == "complete_before_target_assertion"
    assert observation["admission_reached"] and observation["sqlite_control_passed"]
    assert observation["cleanup_returned"] and observation["physical_finished"]
    assert observation["read_count"] == 1 and observation["thread_separated"] is True
    assert observation["native_error_type"] is None
    assert isinstance(outcome, asyncio.CancelledError)
    assert observation["outcome_type"] == "CancelledError"
    assert observation["http_requests"] == [] and observation["http_request_count"] == 0
    assert observation["task_done_after_cleanup"] and observation["client_closed"]
    assert observation["cancellation_return_count"] == cancel_count
    assert (
        observation["held_task_done"] is False
        and observation["cancellation_returns"] == [True] * cancel_count
    )


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Real removed-file failure must win after admitted read cancellation.
async def test_cancelled_template_read_retains_native_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property,
) -> None:
    case: _Case | None = None
    observation = _initial_observation("native_failure", 1)
    try:
        case = await _open_case(tmp_path, monkeypatch)
        observation.update(stage="admission_reached", admission_reached=True)
        cancel_requests, settled_while_held = await _cancel_while_held(case, 1)
        observation.update(
            stage="cancellation_observed",
            cancellation_returns=cancel_requests,
            cancellation_return_count=len(cancel_requests),
            held_task_done=settled_while_held,
        )
        await run_owned_thread(case.template.unlink, label="llama-template-fixture-remove")
        observation.update(stage="template_removed", target_ready=True, file_removed=True)
    finally:
        outcome = await _settle_and_record(case, observation, record_property)

    assert observation["stage"] == "complete_before_target_assertion"
    assert observation["admission_reached"] and observation["file_removed"]
    assert observation["cleanup_returned"] and observation["physical_finished"]
    assert observation["read_count"] == 1 and observation["thread_separated"] is True
    assert observation["native_error_type"] == "FileNotFoundError"
    assert observation["http_requests"] == [] and observation["http_request_count"] == 0
    assert observation["task_done_after_cleanup"] and observation["client_closed"]
    assert observation["cancellation_return_count"] == 1
    assert (
        observation["held_task_done"] is False
        and observation["cancellation_returns"] == [True]
        and isinstance(outcome, FileNotFoundError)
        and observation["outward_is_native_error"] is True
    )


@pytest.mark.contract
@pytest.mark.asyncio
# Layer: contract. A nonmatching template version admits neither file nor HTTP work.
async def test_nonmatching_template_version_does_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: list[str] = []
    requests: list[str] = []
    path_type = type(render_module.QWEN38_TEXT_TEMPLATE_PATH)

    def forbidden_read(path: Path) -> bytes:
        reads.append(str(path))
        raise AssertionError("nonmatching template version read a file")

    monkeypatch.setattr(path_type, "read_bytes", forbidden_read)
    client = _forbidden_http_client(requests)
    try:
        result = await render_module.verify_llama_cpp_render(
            client=client,
            headers={},
            payload=_PAYLOAD,
            template_version="different-template-version",
            context_budget_tokens=64,
        )
    finally:
        await client.aclose()

    assert result == {}
    assert reads == []
    assert requests == []
