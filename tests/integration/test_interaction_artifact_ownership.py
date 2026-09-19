"""Real interaction artifacts, native refusal, verified readback and worker cleanup."""
import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from orket.adapters.storage.interaction_artifact_store import InteractionArtifactStore
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.application.interactions.commit import CommitOrchestrator
from orket.core.contracts.interaction_stream import CommitIntent, StreamEventType
from orket.core.contracts.local_file_lock import LocalFileLockError
from tests.integration.test_interaction_transition_lifetime import owner
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_same_commit_readback_is_idempotent_but_conflict_is_refused(tmp_path):
    first, second = CommitOrchestrator(project_root=tmp_path), CommitOrchestrator(project_root=tmp_path)
    intents = [CommitIntent(type="turn_finalize", ref="original")]
    original = await first.commit(session_id="session", turn_id="turn", intents=intents)
    assert await second.commit(session_id="session", turn_id="turn", intents=intents) == original
    path = Path(original["artifact_refs"][0])
    before = await asyncio.to_thread(path.read_bytes)
    with pytest.raises(ValueError, match="E_INTERACTION_ARTIFACT_CONFLICT"):
        await second.commit(session_id="session", turn_id="turn", intents=[CommitIntent(type="decision", ref="other")])
    assert await asyncio.to_thread(path.read_bytes) == before
    await asyncio.to_thread(path.rename, path.with_suffix(".verified"))


async def test_busy_native_publication_refuses_without_claim(tmp_path):
    path = tmp_path / "workspace/interactions/session/turn/authority_commit.json"
    locks = NativeFileLocks(path, suffix=".owners", error_prefix="E_INTERACTION", empty_key_error="E_INTERACTION_KEY")
    owner = CommitOrchestrator(project_root=tmp_path)
    async with locks.hold("publish"):
        with pytest.raises(LocalFileLockError, match="owner_busy"):
            await owner.commit(session_id="session", turn_id="turn", intents=[])
        assert not await asyncio.to_thread(path.exists)
    assert (await owner.commit(session_id="session", turn_id="turn", intents=[]))["authoritative"]


async def test_another_process_observes_native_owner_then_verified_commit(tmp_path):
    target = tmp_path / "workspace/interactions/session/turn/authority_commit.json"
    locks = NativeFileLocks(target, suffix=".owners", error_prefix="E_INTERACTION", empty_key_error="E_INTERACTION_KEY")
    script = (
        "import asyncio,json,sys;from pathlib import Path;"
        "from orket.application.interactions.commit import CommitOrchestrator;"
        "print(json.dumps(asyncio.run(CommitOrchestrator(project_root=Path(sys.argv[1])).commit("
        "session_id='session',turn_id='turn',intents=[]))))"
    )
    refused, admitted = tmp_path / "refused-process", tmp_path / "admitted-process"
    await asyncio.to_thread(refused.mkdir)
    await asyncio.to_thread(admitted.mkdir)
    async with locks.hold("publish"):
        code, output, error = await child(refused, ["-c", script, str(tmp_path)])
        assert code != 0 and "owner_busy" in error and not output
        assert not await asyncio.to_thread(target.exists)
    code, output, error = await child(admitted, ["-c", script, str(tmp_path)])
    assert code == 0 and not error and json.loads(output)["authoritative"]
    assert json.loads(await asyncio.to_thread(target.read_text, encoding="utf-8"))["session_id"] == "session"


async def test_corrupted_readback_blocks_commit_event_and_every_retry(tmp_path, monkeypatch):
    manager, bus = owner(tmp_path)
    session = await manager.start({})
    turn = await manager.begin_turn(session)
    queue = await bus.subscribe(session)
    replace = Path.replace

    def corrupt_after_replace(path, target):
        result = replace(path, target)
        if Path(target).name == "authority_commit.json":
            Path(target).write_bytes(b"corrupted")
        return result

    monkeypatch.setattr(Path, "replace", corrupt_after_replace)
    try:
        for _ in range(2):
            with pytest.raises(OSError, match="E_INTERACTION_ARTIFACT_UNVERIFIED"):
                await manager.finalize(session, turn)
        events = [queue.get_nowait() for _ in range(queue.qsize())]
        assert [event.event_type for event in events] == [StreamEventType.TURN_FINAL]
        assert (await manager.queries.get_session_status(session))["status"] == "blocked"
        with pytest.raises(RuntimeError, match="teardown failed"):
            await manager.aclose()
    finally:
        await bus.unsubscribe(session, queue)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_finalization_retains_actual_file_worker_and_independent_responsiveness(tmp_path, monkeypatch, stop):
    manager, bus = owner(tmp_path)
    session = await manager.start({})
    turn = await manager.begin_turn(session)
    entered, release = threading.Event(), threading.Event()
    original = InteractionArtifactStore._publish_sync

    def hold(store, session_id, turn_id, name, content):
        if name == "authority_commit.json":
            entered.set()
            assert release.wait(5)
        return original(store, session_id, turn_id, name, content)

    async def invoke():
        if stop == "timeout":
            async with asyncio.timeout(0.1):
                return await manager.finalize(session, turn)
        return await manager.finalize(session, turn)

    monkeypatch.setattr(InteractionArtifactStore, "_publish_sync", hold)
    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 0.5)
        started = time.monotonic()
        assert (await asyncio.wait_for(manager.queries.get_session_status(session), 0.5))["active"]
        assert time.monotonic() - started < 0.5
        if stop == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        assert not task.done()
        settled = time.monotonic()
        release.set()
        with pytest.raises(asyncio.CancelledError if stop == "cancel" else TimeoutError):
            await asyncio.wait_for(task, 3)
        assert time.monotonic() - settled < 3
        assert (await manager.finalize(session, turn)).status == "committed"
        path = tmp_path / "workspace/interactions" / session / turn / "authority_commit.json"
        assert json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))["authoritative"] is True
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await manager.aclose()
