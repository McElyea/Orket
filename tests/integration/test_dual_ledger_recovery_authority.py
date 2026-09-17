"""Recovery must retain uncertain intent and verify the requested durable state."""
import asyncio
import json
from pathlib import Path

import pytest

from tests.helpers.dual_ledger import HeldSQLite, repositories, start_values

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]






def journal_payload(repo, *, kwargs=None):
    return {"schema_version": "2.0", "binding": {
        "sqlite": str(Path(repo.sqlite_repo.db_path).resolve()),
        "protocol": str(repo.protocol_repo.root.resolve()),
    }, "pending": [{"intent_id": "start_run:run", "operation": "start_run", "session_id": "run",
                    "kwargs": kwargs or start_values(), "sqlite_ack": True, "protocol_ack": True,
                    "sqlite_error": None, "protocol_error": None}]}


@pytest.mark.parametrize("raw", ["", " ", '{"pending":[7]}', '{"pending":[{}]}', '{"pending":[]}'])
async def test_corrupt_intent_journal_is_not_empty_or_rewritten(tmp_path, raw):
    """Layer: integration. A malformed on-disk journal refuses recovery before writes."""
    repo = repositories(tmp_path)
    path = repo._intent_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises((RuntimeError, ValueError)):
        await repo.initialize()
    assert path.read_bytes() == before


async def test_database_journals_do_not_share_one_parent_path(tmp_path):
    """Layer: integration. Distinct databases cannot replay one another's intents."""
    first, second = repositories(tmp_path, database="a.db"), repositories(tmp_path, database="b.db")
    assert first._intent_path != second._intent_path


async def test_recovery_does_not_trust_ack_bits_or_existing_row_identity(tmp_path):
    """Layer: integration. Acknowledged metadata cannot erase a content mismatch."""
    repo = repositories(tmp_path)
    await repo.sqlite_repo.start_run(**start_values("other"))
    await repo.protocol_repo.start_run(**start_values("other"))
    path = repo._intent_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(journal_payload(repo)), encoding="utf-8")
    with pytest.raises((RuntimeError, ValueError)):
        await repo.initialize()
    assert json.loads(path.read_bytes())["pending"]
    assert (await repo.sqlite_repo.get_run("run"))["run_name"] == "other"
    assert (await repo.protocol_repo.get_run("run"))["run_name"] == "other"


async def test_conflicting_start_refuses_before_overwriting_either_backend(tmp_path):
    """Layer: integration. Same session identity does not authorize replacing its start."""
    repo = repositories(tmp_path)
    await repo.start_run(**start_values())
    with pytest.raises((RuntimeError, ValueError)):
        await repo.start_run(**start_values("conflict"))
    for backend in (repo.sqlite_repo, repo.protocol_repo):
        assert (await backend.get_run("run"))["run_name"] == "original"




async def test_start_captures_nested_inputs_before_first_await(tmp_path):
    """Layer: integration. Mutation during admitted I/O cannot change either retained start."""
    repo = repositories(tmp_path, sqlite_type=HeldSQLite)
    values = start_values()
    task = asyncio.create_task(repo.start_run(**values))
    await asyncio.wait_for(repo.sqlite_repo.entered.wait(), 2)
    values["summary"]["nested"]["value"] = "changed"
    repo.sqlite_repo.release.set()
    await task
    for backend in (repo.sqlite_repo, repo.protocol_repo):
        assert (await backend.get_run("run"))["summary_json"]["nested"]["value"] == "original"


async def test_cancel_drains_admitted_lifecycle_and_keeps_event_loop_responsive(tmp_path):
    """Layer: integration. Cancellation waits for both actual backends and intent settlement."""
    repo = repositories(tmp_path, sqlite_type=HeldSQLite)
    task = asyncio.create_task(repo.start_run(**start_values()))
    await asyncio.wait_for(repo.sqlite_repo.entered.wait(), 2)
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.sleep(0), 0.5)
        assert not task.done(), "cancel abandoned admitted lifecycle"
    finally:
        repo.sqlite_repo.release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    for backend in (repo.sqlite_repo, repo.protocol_repo):
        assert (await backend.get_run("run"))["run_name"] == "original"
    assert await repo._load_intents() == []
