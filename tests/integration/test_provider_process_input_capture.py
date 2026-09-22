"""Layer: integration. Actual CLI/HTTP/file effects observe provider inputs after admission."""
import asyncio
import json
import os
import sys
import threading
from pathlib import Path

import pytest

from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config import provider_runtime_target as targeting
from tests.integration.test_provider_inventory_inputs import _inventory_server, _options

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).with_name("provider_input_capture_worker.py")


def _roots(tmp_path):
    roots = tmp_path / "original", tmp_path / "changed"
    for root, alias in zip(roots, ("fixture", "unrelated"), strict=True):
        (root / "models").mkdir(parents=True)
        (root / "models" / (alias + ".gguf")).write_bytes(b"inventory fixture; no inference")
    return roots


def _held_inventory(monkeypatch):
    original = targeting.run_owned_thread
    arrived, release = asyncio.Event(), asyncio.Event()

    async def held(operation, **options):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(operation, **options)

    monkeypatch.setattr(targeting, "run_owned_thread", held)
    return arrived, release


def _fixture_cli(monkeypatch, observations):
    original = inventory._run_command_sync

    def fixture_command(cmd, **options):
        assert cmd[0] in {"lms", "ollama"}
        return original([sys.executable, str(WORKER), "inventory", str(observations), *cmd], **options)

    monkeypatch.setattr(inventory, "_run_command_sync", fixture_command)


@pytest.mark.parametrize("explicit", [False, True], ids=["ambient", "explicit"])
@pytest.mark.parametrize("route", ["lmstudio-list", "ollama-resolve", "lmstudio-load"])
async def test_provider_cli_inputs_precede_owned_worker_and_all_inventory_steps(tmp_path, monkeypatch, explicit, route):
    first, second = await asyncio.to_thread(_roots, tmp_path)
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "admitted")
    monkeypatch.setenv("ORKET_PROVIDER_QUARANTINE", "")
    monkeypatch.setenv("ORKET_PROVIDER_MODEL_QUARANTINE", "")
    supplied = dict(os.environ)
    observations = tmp_path / "commands.jsonl"
    _fixture_cli(monkeypatch, observations)
    arrived, release = _held_inventory(monkeypatch)
    options = dict(environment=supplied if explicit else None, timeout_s=5)
    if route == "lmstudio-list":
        call = targeting.list_provider_models(provider="lmstudio", base_url=None, **options)
    else:
        call = targeting.resolve_provider_runtime_target(
            provider="ollama" if route == "ollama-resolve" else "lmstudio", requested_model="",
            base_url=None, auto_select_model=True, auto_load_local_model=True,
            model_load_timeout_s=5, model_ttl_sec=600, **options)
    operation = asyncio.create_task(call)
    try:
        await asyncio.wait_for(arrived.wait(), 5)
        supplied["ORKET_TEST_PROVIDER_INPUT"] = "changed-explicit"
        monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "changed-ambient")
        monkeypatch.chdir(second)
        release.set()
        result = await asyncio.wait_for(asyncio.shield(operation), 15)
        expected = "admitted-original"
        if route == "lmstudio-list":
            assert result["models"] == [expected]
        else:
            assert result.status == "OK" and result.model_id == expected
        rows = [json.loads(line) for line in (await asyncio.to_thread(observations.read_text)).splitlines()]
        assert len(rows) == (4 if route == "lmstudio-load" else 1)
        assert all(row["directory"] == str(first) and row["alias"] == expected for row in rows)
        if route == "lmstudio-load":
            assert result.auto_load_performed and result.loaded_models_after == (expected,)
            assert await asyncio.to_thread((first / "loaded-model.txt").read_text) == expected
            assert not await asyncio.to_thread((second / "loaded-model.txt").exists)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 15)


@pytest.mark.parametrize("route", ["list", "resolve"])
async def test_relative_gguf_root_precedes_http_and_repeated_inventory(tmp_path, monkeypatch, route):
    first, second = await asyncio.to_thread(_roots, tmp_path)
    monkeypatch.chdir(first)
    environment = {"ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": "models"}
    async with _inventory_server() as (url, arrived, release):
        call = (targeting.list_provider_models(provider="llama_cpp", base_url=url, timeout_s=5, environment=environment)
                if route == "list" else targeting.resolve_provider_runtime_target(**_options(url), environment=environment))
        operation = asyncio.create_task(call)
        try:
            await asyncio.wait_for(arrived.wait(), 5)
            monkeypatch.chdir(second)
            release.set()
            result = await asyncio.wait_for(asyncio.shield(operation), 5)
            payload = result if route == "list" else result.to_payload()
            assert payload["gguf_model_root"] == str(first / "models")
            assert payload["gguf_inventory_status"] == "OK"
            assert [row["alias"] for row in payload["gguf_models"]] == ["fixture"]
            if route == "resolve":
                assert result.status == "OK" and result.model_id == "fixture"
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)


@pytest.mark.parametrize("route", ["list", "resolve"])
async def test_sync_provider_entry_captures_before_coroutine_bridge(tmp_path, monkeypatch, route):
    first, second = await asyncio.to_thread(_roots, tmp_path)
    monkeypatch.chdir(first)
    monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "admitted")
    monkeypatch.setenv("ORKET_PROVIDER_QUARANTINE", "")
    monkeypatch.setenv("ORKET_PROVIDER_MODEL_QUARANTINE", "")
    observations = tmp_path / "commands.jsonl"
    _fixture_cli(monkeypatch, observations)
    arrived, release = threading.Event(), threading.Event()
    original = targeting._run_coro_sync

    def held(coroutine):
        arrived.set()
        if not release.wait(5):
            coroutine.close()
            raise AssertionError("Sync bridge fixture release absent")
        return original(coroutine)

    monkeypatch.setattr(targeting, "_run_coro_sync", held)
    options = dict(provider="lmstudio", base_url=None, timeout_s=5)
    if route == "resolve":
        options.update(requested_model="", auto_select_model=True, auto_load_local_model=True,
                       model_load_timeout_s=5, model_ttl_sec=600)
    entry = targeting.list_provider_models_sync if route == "list" else targeting.resolve_provider_runtime_target_sync
    operation = asyncio.create_task(asyncio.to_thread(entry, **options))
    try:
        assert await asyncio.to_thread(arrived.wait, 5)
        monkeypatch.setenv("ORKET_TEST_PROVIDER_INPUT", "changed")
        monkeypatch.chdir(second)
        release.set()
        result = await asyncio.wait_for(asyncio.shield(operation), 15)
        if route == "list":
            assert result["models"] == ["admitted-original"]
        else:
            assert result["model_id"] == "admitted-original" and result["status"] == "OK"
        rows = [json.loads(line) for line in (await asyncio.to_thread(observations.read_text)).splitlines()]
        assert rows and all(row["directory"] == str(first) and row["alias"] == "admitted-original" for row in rows)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 15)
