"""Layer: integration. Real policy observation stays owned until API cleanup finishes."""

import asyncio
import json
import threading
from pathlib import Path

import httpx
import pytest

from orket.adapters.storage.outbound_policy_reader import read_outbound_policy
from orket.application.services import api_runtime_preparation as preparation
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.outbound_policy_probe import policy_app, version

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_two_prepared_apps_keep_file_and_environment_policy_without_rereading(tmp_path, monkeypatch):
    path = tmp_path / "policy.json"
    await asyncio.to_thread(
        path.write_text, json.dumps({"placeholder": "FILE", "pii_field_paths": ["version"]}), encoding="utf-8"
    )
    first = policy_app(tmp_path / "first", {"ORKET_OUTBOUND_POLICY_CONFIG_PATH": str(path)})
    second = policy_app(tmp_path / "second", {"ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS": "api"})
    read, workers = Path.read_bytes, []

    def observed(selected):
        if selected == path:
            workers.append(threading.get_ident())
        return read(selected)

    monkeypatch.setattr(Path, "read_bytes", observed)
    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        assert len(workers) == 1 and workers[0] != threading.get_ident()
        await asyncio.to_thread(path.write_text, '{"pii_field_paths": ["api"]}', encoding="utf-8")
        monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "api,version")
        async with (
            httpx.AsyncClient(transport=httpx.ASGITransport(first), base_url="http://first.test") as a,
            httpx.AsyncClient(transport=httpx.ASGITransport(second), base_url="http://second.test") as b,
        ):
            for _ in range(2):
                responses = await asyncio.gather(version(a), version(b))
                assert all(response.status_code == 200 for response in responses)
                assert responses[0].json() == {"version": "FILE", "api": "v1"}
                assert responses[1].json()["api"] == "[REDACTED]"
                assert responses[1].json()["version"] != "[REDACTED]"
        assert len(workers) == 1
    assert first.state.api_runtime_context.closed and second.state.api_runtime_context.closed


@pytest.mark.parametrize("interruption", ["cancel", "timeout", "read-failure"])
async def test_held_policy_read_stays_owned_through_cancel_timeout_and_cleanup(
    tmp_path, monkeypatch, record_property, interruption
):
    path = tmp_path / "policy.json"
    await asyncio.to_thread(path.write_text, "{}", encoding="utf-8")
    app = policy_app(tmp_path, {"ORKET_OUTBOUND_POLICY_CONFIG_PATH": str(path)})
    entered, release, owners, workers = threading.Event(), threading.Event(), [], []
    read, build = Path.read_bytes, preparation.build_api_runtime_container
    failure = OSError("fixture policy observation failure")

    def construct(*args, **kwargs):
        owner = build(*args, **kwargs)
        owners.append(owner)
        return owner

    def held(selected):
        if selected == path:
            workers.append(threading.get_ident())
            entered.set()
            assert release.wait(10), "policy read was not released"
            if interruption == "read-failure":
                raise failure
        return read(selected)

    async def start():
        async with app.router.lifespan_context(app):
            pytest.fail("interrupted preparation was admitted")

    monkeypatch.setattr(preparation, "build_api_runtime_container", construct)
    monkeypatch.setattr(Path, "read_bytes", held)
    task = asyncio.create_task(start())
    waiter = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        if interruption == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.04)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not task.done() and not app.state.api_ready and not owners[0].closed
        release.set()
        results = await asyncio.wait_for(
            asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        assert (
            results[0] is failure if interruption == "read-failure" else isinstance(results[0], asyncio.CancelledError)
        )
        if waiter:
            assert isinstance(results[1], TimeoutError)
        assert len(owners) == 1 and owners[0].closed and owners[0].engine.kernel_gateway.runtime.closed
        assert workers == [workers[0]] and workers[0] != threading.get_ident()
        assert not app.state.api_ready
    finally:
        release.set()
        await asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True)


@pytest.mark.parametrize(
    "contents,exception",
    [
        (b"[]", ValueError),
        (b"{", ValueError),
        (b"\xff", UnicodeError),
        (b'{"forbidden_patterns":["["]}', ValueError),
        (None, FileNotFoundError),
    ],
)
async def test_invalid_file_observation_closes_acquired_container(tmp_path, monkeypatch, contents, exception):
    path = tmp_path / "policy.json"
    if contents is not None:
        await asyncio.to_thread(path.write_bytes, contents)
    app = policy_app(tmp_path, {"ORKET_OUTBOUND_POLICY_CONFIG_PATH": str(path)})
    build, owners = preparation.build_api_runtime_container, []

    def observe(*args, **kwargs):
        owner = build(*args, **kwargs)
        owners.append(owner)
        return owner

    monkeypatch.setattr(preparation, "build_api_runtime_container", observe)
    with pytest.raises(exception):
        async with app.router.lifespan_context(app):
            pytest.fail("invalid policy was admitted")
    assert len(owners) == 1 and owners[0].closed and not app.state.api_ready


async def test_reader_refuses_loop_and_non_absolute_paths(tmp_path):
    with pytest.raises(RuntimeError, match="E_OUTBOUND_POLICY_REQUIRES_ASYNC_OWNER"):
        read_outbound_policy(tmp_path / "absent.json")
    with pytest.raises(ValueError, match="E_OUTBOUND_POLICY_ABSOLUTE_PATH_REQUIRED"):
        await asyncio.to_thread(read_outbound_policy, Path("policy.json"))
    with pytest.raises(FileNotFoundError):
        await asyncio.to_thread(read_outbound_policy, tmp_path / "absent.json")
