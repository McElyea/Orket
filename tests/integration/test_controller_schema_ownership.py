"""Integration: selected schema bytes and validation inputs belong to each call."""
from __future__ import annotations

import asyncio
import json
import threading

import pytest

from orket.extensions import controller_observability as owner

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_explicit_schema_selection_and_replacement_are_observed(tmp_path):
    allow, deny = tmp_path / "allow.json", tmp_path / "deny.json"
    allow.write_text('{"type":"object"}', encoding="utf-8")
    deny.write_text('{"not":{}}', encoding="utf-8")
    await owner.validate_observability_schema([{}], schema_path=allow)
    with pytest.raises(ValueError, match="controller.observability_schema_invalid:index=0"):
        await owner.validate_observability_schema([{}], schema_path=deny)
    allow.write_bytes(deny.read_bytes())
    with pytest.raises(ValueError, match="controller.observability_schema_invalid:index=0"):
        await owner.validate_observability_schema([{}], schema_path=allow)
    with pytest.raises(ValueError, match="controller.observability_schema_invalid:index=0"):
        await owner.validate_observability_schema([{}])


@pytest.mark.parametrize("stop", ["cancel", "caller-timeout", "complete"])
async def test_schema_read_is_owned_and_captures_nested_events(tmp_path, monkeypatch, stop):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"properties": {"nested": {"const": {"value": "captured"}}}}), encoding="utf-8")
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = owner.read_controller_schema

    def held(path):
        entered.set()
        try:
            if not release.wait(10):
                raise RuntimeError("schema worker was not released")
            return original(path)
        finally:
            settled.set()

    monkeypatch.setattr(owner, "read_controller_schema", held)
    event = {"nested": {"value": "captured"}}
    task = asyncio.create_task(owner.validate_observability_schema([event], schema_path=schema))
    timeout_owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        event["nested"]["value"] = "mutated after admission"
        if stop == "cancel":
            task.cancel()
        elif stop == "caller-timeout":
            timeout_owner = asyncio.create_task(asyncio.wait_for(task, .01))
        await asyncio.wait_for(asyncio.sleep(.03), .5)
        assert not task.done() and not settled.is_set()
        if stop != "complete":
            assert task.cancelling() == 1
        if stop == "cancel":
            task.cancel()
        release.set()
        if stop == "complete":
            await asyncio.wait_for(task, 5)
        else:
            with pytest.raises(TimeoutError if stop == "caller-timeout" else asyncio.CancelledError):
                await asyncio.wait_for(timeout_owner or task, 5)
        assert settled.is_set()
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, *([timeout_owner] if timeout_owner else []), return_exceptions=True)


@pytest.mark.parametrize("root", [None, [], [{}], "schema", 1])
# Layer: integration
async def test_selected_schema_rejects_invalid_json_root(tmp_path, root):
    path = tmp_path / "invalid-root.json"
    await asyncio.to_thread(path.write_text, json.dumps(root), encoding="utf-8")
    with pytest.raises(ValueError, match="controller.observability_schema_root_invalid"):
        await owner.validate_observability_schema([{}], schema_path=path)


@pytest.mark.parametrize("admitted", [True, False])
# Layer: integration
async def test_selected_boolean_schema_keeps_its_validation_semantics(tmp_path, admitted):
    path = tmp_path / "boolean-schema.json"
    await asyncio.to_thread(path.write_text, json.dumps(admitted), encoding="utf-8")
    if admitted:
        await owner.validate_observability_schema([{}], schema_path=path)
    else:
        with pytest.raises(ValueError, match="controller.observability_schema_invalid:index=0"):
            await owner.validate_observability_schema([{}], schema_path=path)
