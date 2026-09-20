"""Integration: real interaction ownership and captured workload publication inputs."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from orket.core.contracts.interaction_stream import StreamEventType
from orket.extensions.manager import ExtensionManager
from tests.helpers.interactions import create_interaction_manager
from tests.integration.test_sdk_process_control_plane import admitted_sdk as admitted_sdk
from tests.integration.test_workload_publication_ownership import _hold_worker
from tests.runtime.test_extension_manager import _init_test_extension_repo

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def admitted_legacy(tmp_path):
    repo = tmp_path / "legacy-source"
    repo.mkdir()
    _init_test_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "legacy-catalog.json", project_root=tmp_path)
    asyncio.run(manager.install_from_repo(str(repo)))
    return manager, {"seed": 1}


@pytest.mark.parametrize("family", ["sdk", "legacy"])
async def test_real_interaction_owner_finalizes_after_workload_publication(tmp_path, admitted_sdk, admitted_legacy, family):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    workload_id = "fixture" if family == "sdk" else "mystery_v1"
    interactions = create_interaction_manager(tmp_path)
    session_id = await interactions.start()
    queue = await interactions.bus.subscribe(session_id)
    try:
        turn_id = await interactions.begin_turn(session_id)
        context = await interactions.create_context(session_id, turn_id)
        result = await manager.run_workload(workload_id=workload_id, input_config=payload, workspace=tmp_path,
                                            department="core", interaction_context=context)
        provenance = json.loads(await asyncio.to_thread(Path(result.provenance_path).read_text, encoding="utf-8"))
        assert provenance["control_plane"]
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        assert not any(event.event_type in {StreamEventType.TURN_FINAL, StreamEventType.COMMIT_FINAL} for event in events)
        await interactions.finalize(session_id, turn_id)
        final_events = []
        while not queue.empty():
            final_events.append(queue.get_nowait())
        assert [event.event_type for event in final_events] == [StreamEventType.TURN_FINAL, StreamEventType.COMMIT_FINAL]
        assert final_events[-1].payload["authoritative"] is True
    finally:
        await interactions.bus.unsubscribe(session_id, queue)
        await interactions.aclose()


@pytest.mark.parametrize("family", ["sdk", "legacy"])
async def test_sdk_publication_uses_input_captured_before_worker(tmp_path, admitted_sdk, admitted_legacy, monkeypatch, family):
    manager, payload = admitted_sdk if family == "sdk" else admitted_legacy
    payload["nested"] = {"value": "admitted"}
    expected_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    entered, release, settled = _hold_worker(monkeypatch, manager, "manifest-build", legacy=family == "legacy")
    task = asyncio.create_task(manager.run_workload(workload_id="fixture" if family == "sdk" else "mystery_v1", input_config=payload,
                                                  workspace=tmp_path, department="core"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        payload["nested"]["value"] = "mutated"
        release.set()
        result = await asyncio.wait_for(task, 5)
        provenance = json.loads(await asyncio.to_thread(Path(result.provenance_path).read_text, encoding="utf-8"))
        if family == "sdk":
            assert result.plan_hash == expected_digest
        assert provenance["input_config_digest"] == expected_digest
        assert provenance["input_config_redacted"]["payload_digest_sha256"] == expected_digest
    finally:
        release.set()
        if entered.is_set():
            assert await asyncio.to_thread(settled.wait, 5)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
