"""Integration: actual evidence files and caller ordering; supplied model output is a fixture."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services import outward_model_observability as evidence
from orket.application.services.outward_model_tool_call_service import OutwardModelToolCallService
from tests.helpers.evidence_ownership import (
    hold_native_call,
    model_evidence_directory,
    model_evidence_inputs,
    settle_evidence,
    timeout_evidence_while_held,
)
from tests.helpers.outward_model import FakeOutwardModelClient
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_stream,
    sqlite_response,
    wait_entered,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
REFERENCES = (("model_invocation_ref", "model_invocation_sha256"),
              ("model_prompt_ref", "model_prompt_redacted_sha256"),
              ("model_response_ref", "model_response_redacted_sha256"),
              ("proposal_extraction_ref", "proposal_extraction_sha256"))


async def read_document(path):
    return json.loads(await asyncio.to_thread(path.read_bytes))


async def verify_independent_digests(root, result):
    for ref, digest in REFERENCES:
        material = await asyncio.to_thread((root / result.model_invocation[ref]).read_bytes)
        assert hashlib.sha256(material).hexdigest() == result.model_invocation[digest]


@pytest.mark.parametrize("operation", ["open", "write", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_publication_retains_native_attempt_and_ordered_batch(
    tmp_path, monkeypatch, record_property, operation, stop, legacy,
):
    inputs = model_evidence_inputs(tmp_path)
    inputs["evidence_scope"] = None if legacy else inputs["evidence_scope"]
    directory = model_evidence_directory(tmp_path, inputs["evidence_scope"])
    first = directory / "model_prompt_redacted_turn_1.json"
    hold = hold_stream(monkeypatch, first, operation)
    task = asyncio.create_task(evidence.write_model_evidence(**inputs))
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
        await interrupt(task, hold, tmp_path / "responsive.sqlite3", record_property)
        assert hold.thread != threading.get_ident()
        assert hold.streams and all(stream.closed for stream in hold.streams)
        for stem in ("model_prompt_redacted", "model_response_redacted", "proposal_extraction", "model_invocation"):
            material = await asyncio.to_thread((directory / f"{stem}_turn_1.json").read_bytes)
            assert json.loads(material)["run_id"] == "native-run"
            if legacy:
                assert await asyncio.to_thread((directory / f"{stem}.json").read_bytes) == material
            else:
                assert not await asyncio.to_thread((directory / f"{stem}.json").exists)
    finally:
        await settle_evidence(task, hold)


async def test_publication_captures_nested_inputs_before_native_admission(tmp_path, monkeypatch):
    inputs = model_evidence_inputs(tmp_path)
    hold = hold_native_call(monkeypatch, evidence, "_evidence_dir")
    task = asyncio.create_task(evidence.write_model_evidence(**inputs))
    try:
        await wait_entered(hold)
        inputs["messages"][0]["content"] = "mutated prompt"
        inputs["runtime_context"]["native_tools"][0]["function"]["name"] = "mutated-tool"
        inputs["response"].raw["usage"]["prompt_tokens"] = 999
        inputs["tool_call"]["args"]["content"] = "mutated content"
        hold.release.set()
        result = await task
        prompt = await read_document(tmp_path / result.model_invocation["model_prompt_ref"])
        response = await read_document(tmp_path / result.model_invocation["model_response_ref"])
        assert prompt["messages"][0]["content"] == "original prompt"
        assert prompt["runtime_context"]["native_tools"][0]["function"]["name"] == "original-tool"
        assert response["extracted_tool_call_redacted"]["args"]["content"] == "original content"
        assert result.model_invocation["prompt_token_count"] == 5
        await verify_independent_digests(tmp_path, result)
    finally:
        await settle_evidence(task, hold)


async def test_publication_binds_relative_root_before_native_admission(tmp_path, monkeypatch):
    other = tmp_path / "other"
    await asyncio.to_thread(other.mkdir)
    monkeypatch.chdir(tmp_path)
    inputs = model_evidence_inputs(Path())
    hold = hold_native_call(monkeypatch, evidence, "_evidence_dir")
    task = asyncio.create_task(evidence.write_model_evidence(**inputs))
    try:
        await wait_entered(hold)
        monkeypatch.chdir(other)
        hold.release.set()
        result = await task
        assert result.directory == model_evidence_directory(tmp_path)
        assert not await asyncio.to_thread(model_evidence_directory(other).exists)
        await verify_independent_digests(tmp_path, result)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("operation", ["read", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_evidence_verification_retains_real_read_and_close(tmp_path, monkeypatch, record_property, operation, stop):
    result = await evidence.write_model_evidence(**model_evidence_inputs(tmp_path))
    selected = tmp_path / result.model_invocation["model_invocation_ref"]
    hold = hold_stream(monkeypatch, selected, operation)
    task = asyncio.create_task(evidence.verify_model_evidence(workspace_root=tmp_path, evidence=result.model_invocation))
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
        await interrupt(task, hold, tmp_path / "responsive.sqlite3", record_property)
        assert hold.thread != threading.get_ident()
        assert hold.streams and all(stream.closed for stream in hold.streams)
    finally:
        await settle_evidence(task, hold)


async def test_verification_captures_all_references_before_first_read(tmp_path, monkeypatch):
    result = await evidence.write_model_evidence(**model_evidence_inputs(tmp_path))
    selected = tmp_path / result.model_invocation["model_invocation_ref"]
    hold = hold_stream(monkeypatch, selected, "read")
    borrowed = dict(result.model_invocation)
    task = asyncio.create_task(evidence.verify_model_evidence(workspace_root=tmp_path, evidence=borrowed))
    try:
        await wait_entered(hold)
        borrowed["model_prompt_ref"] = "later-missing.json"
        borrowed["model_prompt_redacted_sha256"] = "0" * 64
        hold.release.set()
        assert await task is None
        assert all(stream.closed for stream in hold.streams)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("operation", ["read", "close"])
async def test_verification_native_failure_survives_cancellation(tmp_path, monkeypatch, operation):
    result = await evidence.write_model_evidence(**model_evidence_inputs(tmp_path))
    selected = tmp_path / result.model_invocation["model_invocation_ref"]
    hold = hold_stream(monkeypatch, selected, operation, failure=True)
    task = asyncio.create_task(evidence.verify_model_evidence(workspace_root=tmp_path, evidence=result.model_invocation))
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done(), "verification failure escaped before native settlement"
        hold.release.set()
        with pytest.raises(evidence.OutwardModelObservabilityError, match="E_OUTWARD_MODEL_EVIDENCE_UNAVAILABLE") as failure:
            await task
        assert isinstance(failure.value.__cause__, OSError)
        assert hold.finished.is_set() and all(stream.closed for stream in hold.streams)
    finally:
        await settle_evidence(task, hold)


async def test_prompt_bytes_keep_declared_format_and_native_newline(tmp_path):
    result = await evidence.write_model_evidence(**model_evidence_inputs(tmp_path))
    expected = {"schema_version": "outward_model_prompt_redacted.v1", "run_id": "native-run",
        "namespace": "native-owner", "turn_number": 1,
        "messages": [{"role": "user", "content": "original prompt"}],
        "runtime_context": {"local_prompt_task_class": None, "required_action_tools": [],
            "native_tool_choice": None, "outward_run_id": None, "outward_namespace": None,
            "turn_number": None, "native_tools": [{"function": {"name": "original-tool"}}]}}
    raw = await asyncio.to_thread((tmp_path / result.model_invocation["model_prompt_ref"]).read_bytes)
    assert raw == (json.dumps(expected, indent=2, sort_keys=True) + "\n").replace("\n", os.linesep).encode("utf-8")
    await verify_independent_digests(tmp_path, result)


@pytest.mark.parametrize("damage,code", [("missing", "REQUIRED"), ("escape", "SCOPE"),
                                        ("unavailable", "UNAVAILABLE"), ("digest", "DIGEST")])
async def test_verification_refuses_changed_or_invalid_evidence(tmp_path, damage, code):
    result = await evidence.write_model_evidence(**model_evidence_inputs(tmp_path))
    borrowed = dict(result.model_invocation)
    if damage == "missing":
        borrowed.pop("model_invocation_ref")
    elif damage == "escape":
        borrowed["model_invocation_ref"] = "../outside.json"
    elif damage == "unavailable":
        await asyncio.to_thread((tmp_path / borrowed["model_invocation_ref"]).unlink)
    else:
        await asyncio.to_thread((tmp_path / borrowed["model_invocation_ref"]).write_bytes, b'{"changed":true}')
    with pytest.raises(evidence.OutwardModelObservabilityError, match="E_OUTWARD_MODEL_EVIDENCE_" + code):
        await evidence.verify_model_evidence(workspace_root=tmp_path, evidence=borrowed)


async def test_failed_publication_preserves_partial_effect_and_exclusive_scope(tmp_path, monkeypatch):
    inputs = model_evidence_inputs(tmp_path)
    directory = model_evidence_directory(tmp_path)
    selected = directory / "model_response_redacted_turn_1.json"
    hold = hold_stream(monkeypatch, selected, "write", failure=True)
    task = asyncio.create_task(evidence.write_model_evidence(**inputs))
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done(), "partial publication escaped its native failure"
        hold.release.set()
        with pytest.raises(evidence.OutwardModelObservabilityError, match="model observability write failed") as failure:
            await task
        assert isinstance(failure.value.__cause__, OSError)
        assert hold.streams and all(stream.closed for stream in hold.streams)
        before = await asyncio.to_thread(selected.read_bytes)
        assert before and await asyncio.to_thread((directory / "model_prompt_redacted_turn_1.json").is_file)
        assert not await asyncio.to_thread((directory / "model_invocation_turn_1.json").exists)
        with pytest.raises(evidence.OutwardModelObservabilityError, match="model observability write failed"):
            await evidence.write_model_evidence(**inputs)
        assert await asyncio.to_thread(selected.read_bytes) == before
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_model_caller_waits_for_evidence_close_before_client_close_or_result(
    tmp_path, monkeypatch, record_property, stop,
):
    inputs = model_evidence_inputs(tmp_path)
    client = FakeOutwardModelClient(args=inputs["tool_call"]["args"])
    service = OutwardModelToolCallService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
                                        workspace_root=tmp_path, model_client_factory=lambda: client)
    hold = hold_stream(monkeypatch, model_evidence_directory(tmp_path) / "model_invocation_turn_1.json", "close")
    task = asyncio.create_task(service.produce_governed_tool_call(run=inputs["run"], expected_tool="write_file",
        governed_tools={"write_file"}, evidence_scope=inputs["evidence_scope"]))
    try:
        await wait_entered(hold)
        assert not client.closed and not task.done()
        assert await sqlite_response(tmp_path / "responsive.sqlite3", record_property) < 0.5
        if stop == "none":
            hold.release.set()
            result = await task
            assert result.tool_call == inputs["tool_call"]
        else:
            interrupt = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
            await interrupt(task, hold, tmp_path / "responsive.sqlite3", record_property)
        assert hold.finished.is_set() and all(stream.closed for stream in hold.streams)
        assert client.closed
        assert not await asyncio.to_thread((tmp_path / "proposal-only.txt").exists)
    finally:
        await settle_evidence(task, hold)
