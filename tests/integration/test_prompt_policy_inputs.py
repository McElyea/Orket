"""Layer: integration. Actual registry reads with controlled request mutation and interruption."""
import asyncio
import hashlib
import json
import os
import threading
from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError

import pytest

from orket.application.services import local_prompting_service as policy
from orket.application.services.local_model_factory import (
    create_local_model_provider_async,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def held_read(monkeypatch, *, fail=False):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = policy.read_prompt_registry

    def held(path):
        entered.set()
        try:
            assert release.wait(5), "worker release was not delivered"
            observed = original(path)
            if fail:
                raise OSError("controlled registry read failure")
            return observed
        finally:
            finished.set()

    monkeypatch.setattr(policy, "read_prompt_registry", held)
    try:
        yield entered, release, finished
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(finished.wait, 5)


async def test_messages_and_nested_context_are_captured_before_registry_read(monkeypatch):
    service = policy.LocalPromptingService(environment={})
    messages = [{"role": "system", "content": "captured"}, {"role": "user", "content": "Issue Brief:\ncaptured"}]
    context = {"required_action_tools": ["write_file"], "required_write_paths": ["one.py"]}
    async with held_read(monkeypatch) as (entered, release, _):
        task = asyncio.create_task(service.resolve(provider_backend="openai_compat", model="gemma-3-12b",
                                                   messages=messages, runtime_context=context))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            messages[1]["content"] = "Issue Brief:\nMUTATED"
            context["required_write_paths"].append("two.py")
            release.set()
            result = await task
            assert result.context_budget_tokens > 2400
            assert "captured" in str(result.messages) and "MUTATED" not in str(result.messages)
            assert "two.py" not in str(result.messages)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


async def test_service_captures_explicit_and_process_session_settings(monkeypatch):
    settings = {"ORKET_LMSTUDIO_SESSION_MODE": "fixed", "ORKET_LMSTUDIO_SESSION_ID": "captured"}
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    services = [policy.LocalPromptingService(environment=settings), policy.LocalPromptingService()]
    settings["ORKET_LMSTUDIO_SESSION_ID"] = "caller mutation"
    async with held_read(monkeypatch) as (entered, release, _):
        tasks = [asyncio.create_task(service.resolve(provider_backend="openai_compat", model="qwen2.5:7b",
                        messages=[{"role": "user", "content": "hello"}])) for service in services]
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            monkeypatch.setenv("ORKET_LMSTUDIO_SESSION_ID", "process mutation")
            release.set()
            assert [result.lmstudio_session_id for result in await asyncio.gather(*tasks)] == ["captured", "captured"]
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)


async def test_parsed_registry_and_digest_share_one_read_even_when_file_replaced(tmp_path, monkeypatch):
    original = policy.read_prompt_registry
    initial = await asyncio.to_thread(policy.DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH.read_bytes)
    path = tmp_path / "profiles.json"
    await asyncio.to_thread(path.write_bytes, initial)
    reads = []

    def replace_after_read(path):
        observation = original(path)
        reads.append(observation)
        payload = json.loads(initial)
        for entry in payload["profiles"]:
            entry["profile"]["template_version"] = "changed-after-read"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return observation

    monkeypatch.setattr(policy, "read_prompt_registry", replace_after_read)
    result = await policy.LocalPromptingService(environment={}).resolve(provider_backend="ollama", model="qwen2.5:7b",
        messages=[{"role": "user", "content": "hello"}], runtime_context={"local_prompt_profile_registry_path": str(path)})
    assert len(reads) == 1 and result.template_version != "changed-after-read"
    assert result.profile_registry_snapshot_hash == hashlib.sha256(initial).hexdigest()


async def test_same_size_and_mtime_registry_replacement_is_observed(tmp_path):
    path = tmp_path / "profiles.json"
    initial = await asyncio.to_thread(policy.DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH.read_bytes)
    await asyncio.to_thread(path.write_bytes, initial)
    stat = await asyncio.to_thread(path.stat)
    service = policy.LocalPromptingService(environment={"ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH": str(path)})
    options = dict(provider_backend="ollama", model="qwen2.5:7b", messages=[{"role": "user", "content": "hello"}])
    first = await service.resolve(**options)
    replaced = initial.replace(b'"temperature": 0.2', b'"temperature": 0.4')
    assert replaced != initial and len(replaced) == len(initial)
    await asyncio.to_thread(path.write_bytes, replaced)
    await asyncio.to_thread(os.utime, path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    second = await service.resolve(**options)
    assert first.profile_registry_snapshot_hash == hashlib.sha256(initial).hexdigest()
    assert second.profile_registry_snapshot_hash == hashlib.sha256(replaced).hexdigest()


@pytest.mark.parametrize("fail", [False, True], ids=["read-success", "read-failure"])
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_interruption_retains_worker_and_preserves_observed_failure(monkeypatch, fail, interrupt):
    async with held_read(monkeypatch, fail=fail) as (entered, release, finished):
        task = asyncio.create_task(policy.LocalPromptingService(environment={}).resolve(provider_backend="ollama",
            model="qwen2.5:7b", messages=[{"role": "user", "content": "hello"}]))
        waiter = task
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            if interrupt == "timeout":
                waiter = asyncio.create_task(asyncio.wait_for(task, timeout=.01))
                await asyncio.sleep(.03)
            else:
                for _ in range(2):
                    task.cancel()
                    await asyncio.sleep(.01)
            assert not task.done() and not waiter.done() and not finished.is_set()
            release.set()
            expected = OSError if fail else (TimeoutError if interrupt == "timeout" else asyncio.CancelledError)
            with pytest.raises(expected):
                await waiter
            assert finished.is_set()
        finally:
            release.set()
            await asyncio.gather(waiter, task, return_exceptions=True)


async def test_policy_is_immutable_and_payload_exports_do_not_alias():
    service = policy.LocalPromptingService(environment={})
    options = dict(provider_backend="ollama", model="qwen2.5:7b", messages=[{"role": "user", "content": "hello"}])
    result = await service.resolve(**options)
    expected = result.telemetry()
    with pytest.raises(FrozenInstanceError):
        result.mode = "enforce"
    with pytest.raises(TypeError):
        result.messages[0]["content"] = "MUTATED"
    with pytest.raises(TypeError):
        result.sampling_bundle["temperature"] = 99
    exported = result.telemetry()
    exported["stop_sequences_by_task_class"]["concise_text"].append("MUTATED")
    result.message_payload()[0]["content"] = "MUTATED"
    assert result.telemetry() == expected
    assert result.messages[0]["content"] == "hello"
    assert (await service.resolve(**options)).telemetry() == expected


async def test_provider_captures_request_before_runtime_target_await(monkeypatch):
    # Controlled target wait; actual policy and HTTP translation are exercised separately.
    from orket.adapters.llm import local_model_provider as adapter
    entered, release = asyncio.Event(), asyncio.Event()

    async def held(provider):
        entered.set()
        await release.wait()
        return provider.model

    monkeypatch.setattr(adapter, "ensure_provider_runtime_target", held)
    provider = (await create_local_model_provider_async(model="qwen2.5:7b", provider="openai_compat", environment={}))
    observed = []

    async def transport(messages, selected_policy, **kwargs):
        observed.append((messages, kwargs["runtime_context"]))
        return adapter.ModelResponse("controlled", {})

    monkeypatch.setattr(provider, "_complete_openai_compat", transport)
    messages = [{"role": "user", "content": "captured"}]
    context = {"required_write_paths": ["first.py"]}
    task = asyncio.create_task(provider.complete(messages, context))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        messages[0]["content"] = "MUTATED"
        context["required_write_paths"].append("second.py")
        release.set()
        await task
        assert "MUTATED" not in observed[0][0][0]["content"]
        assert observed[0][1]["required_write_paths"] == ["first.py"]
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await provider.close()


@asynccontextmanager
async def http_provider(observed):
    owners, errors = set(), []

    async def respond(reader, writer):
        task = asyncio.current_task()
        owners.add(task)
        try:
            headers = (await reader.readuntil(b"\r\n\r\n")).decode()
            length = next((int(line.split(":", 1)[1]) for line in headers.splitlines()
                           if line.lower().startswith("content-length:")), 0)
            body = await reader.readexactly(length)
            if headers.startswith("GET /v1/models "):
                payload = {"data": [{"id": "qwen2.5:7b"}]}
            else:
                assert headers.startswith("POST /v1/chat/completions ")
                observed.append(json.loads(body))
                payload = {"model": "qwen2.5:7b", "choices": [{"message": {"content": "controlled response"}}]}
            raw = json.dumps(payload).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         + f"Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode() + raw)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, AssertionError) as exc:
            errors.append(exc)
        finally:
            writer.close()
            await writer.wait_closed()
            owners.remove(task)

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1"
    finally:
        server.close()
        await server.wait_closed()
        if owners:
            await asyncio.wait_for(asyncio.gather(*owners), timeout=5)
        assert not owners and not errors


async def test_captured_policy_reaches_actual_http_transport(monkeypatch):
    observed = []
    settings = {"ORKET_LOCAL_PROMPTING_MODE": "compat", "ORKET_LMSTUDIO_SESSION_MODE": "fixed",
                "ORKET_LMSTUDIO_SESSION_ID": "captured-session",
                "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false",
                "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false"}
    async with http_provider(observed) as url:
        provider = (await create_local_model_provider_async(model="qwen2.5:7b", provider="openai_compat",
                                               base_url=url, environment=settings))
        settings["ORKET_LMSTUDIO_SESSION_ID"] = "MUTATED"
        monkeypatch.setenv("ORKET_LOCAL_PROMPT_PROFILE_ID", "missing-profile")
        monkeypatch.setenv("ORKET_LMSTUDIO_SESSION_ID", "MUTATED")
        try:
            response = await provider.complete([{"role": "user", "content": "hello"}],
                {"local_prompt_max_output_tokens": 9, "local_prompt_stop_sequences": [" END\n"]})
            assert response.content == "controlled response"
            assert response.raw["profile_resolution_path"] == "matched"
            assert response.raw["local_prompting_mode"] == "compat"
            expected = await asyncio.to_thread(policy.DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH.read_bytes)
            assert response.raw["profile_registry_snapshot_hash"] == hashlib.sha256(expected).hexdigest()
        finally:
            await provider.close()
        assert provider.client.is_closed
    assert len(observed) == 1 and observed[0]["session_id"] == "captured-session"
    assert observed[0]["max_tokens"] == 9 and observed[0]["stop"][0] == " END\n"
