"""Migration, transaction rollback and concurrent ownership on real card stores."""
from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.card_migrations import CARD_BOOTSTRAP_MIGRATIONS, CARD_SCHEMA_USER_VERSION
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import (
    complete_existing_card,
    completion_components,
    completion_definition,
    write_completion_source,
)

pytestmark = pytest.mark.integration


async def _prepared(tmp_path):
    repo, service = completion_components(tmp_path / "cards.sqlite3", tmp_path / "workspace")
    await write_completion_source(service.workspace_root)
    await repo.save(IssueRecord(id="card", summary="Increment", seat="developer", status=CardStatus.CODE_REVIEW,
                                params={"completion_acceptance": completion_definition().model_dump(mode="json")}))
    context = await service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt")
    return repo, service, await service.evaluate_attempt(repo, context)


async def _receipt_count(repo):
    async with aiosqlite.connect(repo.db_path) as conn:
        return (await (await conn.execute("SELECT count(*) FROM card_completion_commits")).fetchone())[0]


@pytest.mark.asyncio
# Layer: integration
async def test_failed_status_write_rolls_back_accepted_receipt_and_history(tmp_path):
    repo, _, result = await _prepared(tmp_path)
    async with aiosqlite.connect(repo.db_path) as conn:
        await conn.execute("CREATE TRIGGER refuse_completion BEFORE UPDATE OF status ON issues "
                           "WHEN NEW.status='done' BEGIN SELECT RAISE(ABORT, 'injected_write_failure'); END")
        await conn.commit()
    with pytest.raises(aiosqlite.IntegrityError, match="injected_write_failure"):
        await repo.update_status("card", CardStatus.DONE, completion_request=result.request)
    assert await _receipt_count(repo) == 0
    assert await repo.get_card_history("card") == []
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW


class PausedAuthority:
    """Pause after the real application inspection to observe transaction ordering."""

    def __init__(self, service):
        self.service = service
        self.inspected = asyncio.Event()
        self.release = asyncio.Event()

    async def authorize_completion(self, **kwargs):
        decision = await self.service.authorize_completion(**kwargs)
        self.inspected.set()
        await self.release.wait()
        return decision


@pytest.mark.asyncio
# Layer: integration
async def test_input_writer_waits_for_final_review_transaction_then_reopens_card(tmp_path):
    repo, service, result = await _prepared(tmp_path)
    authority = PausedAuthority(service)
    completer = AsyncCardRepository(repo.db_path, completion_authority=authority)
    stale_record = await repo.get_by_id("card")
    stale_record.summary = "Changed after verification"
    completing = asyncio.create_task(completer.update_status("card", CardStatus.DONE, completion_request=result.request))
    await asyncio.wait_for(authority.inspected.wait(), timeout=5)
    changing = asyncio.create_task(repo.save(stale_record))
    try:
        finished, _ = await asyncio.wait({changing}, timeout=0.1)
        assert not finished
        # An initialized WAL reader sees the previously committed card during review.
        assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW
    finally:
        authority.release.set()
        await asyncio.gather(completing, changing)
    changed = await repo.get_by_id("card")
    assert changed.summary == stale_record.summary and changed.status == CardStatus.CODE_REVIEW
    assert changed.completion_context is None and changed.completion_ref is None
    assert await _receipt_count(repo) == 1


@pytest.mark.asyncio
# Layer: integration
async def test_cancellation_during_final_inspection_does_not_commit_and_releases_writer(tmp_path):
    repo, service, result = await _prepared(tmp_path)
    authority = PausedAuthority(service)
    completer = AsyncCardRepository(repo.db_path, completion_authority=authority)
    completing = asyncio.create_task(completer.update_status("card", CardStatus.DONE, completion_request=result.request))
    await asyncio.wait_for(authority.inspected.wait(), timeout=5)
    completing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await completing
    assert await _receipt_count(repo) == 0
    assert (await repo.get_by_id("card")).status == CardStatus.CODE_REVIEW
    await repo.update_status("card", CardStatus.BLOCKED)
    assert (await repo.get_by_id("card")).status == CardStatus.BLOCKED


@pytest.mark.asyncio
# Layer: integration
async def test_migration_preserves_legacy_terminal_history_without_creating_acceptance(tmp_path):
    db = tmp_path / "legacy.sqlite3"
    async with aiosqlite.connect(db) as conn:
        await SQLiteMigrationRunner(namespace="card_repository").apply(conn, CARD_BOOTSTRAP_MIGRATIONS)
        await conn.execute("INSERT INTO issues (id, summary, seat, type, priority, status, params_json) "
                           "VALUES (?, ?, ?, 'issue', 2.0, ?, ?)",
                           ("old", "Legacy completion", "developer", "done", '{"b": 2, "a": 1}'))
        await conn.execute("INSERT INTO card_transactions (card_id, role, action) VALUES ('old', 'system', 'Legacy done')")
        await conn.execute("PRAGMA user_version=1")
        await conn.commit()
    repo = AsyncCardRepository(db)
    old = await repo.get_by_id("old")
    assert old.status == CardStatus.DONE and old.completion_generation == 0
    assert old.completion_context is None and old.completion_ref is None
    assert await _receipt_count(repo) == 0
    old.note = "Historical support annotation"
    await repo.save(old)
    assert "Legacy done" in (await repo.get_card_history("old"))[0]
    with pytest.raises(CardCompletionRejected, match="AUTHORITY_MISSING"):
        await repo.update_status("old", CardStatus.DONE)
    async with aiosqlite.connect(db) as conn:
        assert (await (await conn.execute("PRAGMA user_version")).fetchone())[0] == CARD_SCHEMA_USER_VERSION
        assert (await (await conn.execute("SELECT params_json FROM issues WHERE id='old'")).fetchone())[0] == '{"b": 2, "a": 1}'
    await repo.update_status("old", CardStatus.CODE_REVIEW)
    await complete_existing_card(repo, "old", tmp_path / "workspace")
    assert (await repo.get_by_id("old")).completion_ref is not None


@pytest.mark.asyncio
# Layer: integration
async def test_successful_receipt_is_immutable_and_input_changes_require_reopening(tmp_path):
    repo, _, result = await _prepared(tmp_path)
    await repo.update_status("card", CardStatus.DONE, completion_request=result.request)
    async with aiosqlite.connect(repo.db_path) as conn:
        for statement in ("UPDATE card_completion_commits SET receipt_json='{}'", "DELETE FROM card_completion_commits",
                          "UPDATE issues SET summary='changed'", "UPDATE issues SET completion_generation=999"):
            with pytest.raises(aiosqlite.IntegrityError):
                await conn.execute(statement)
    completed = await repo.get_by_id("card")
    completed.summary = "Different objective"
    with pytest.raises(CardCompletionRejected, match="SAVE_REQUIRES_REVIEW"):
        await repo.save(completed)
    assert (await repo.get_by_id("card")).summary == "Increment"


@pytest.mark.asyncio
# Layer: integration
async def test_nonterminal_same_status_keeps_history_and_active_acceptance_binding(tmp_path):
    repo, _, result = await _prepared(tmp_path)
    before = await repo.get_by_id("card")
    await repo.update_status("card", CardStatus.CODE_REVIEW, reason="review_dispatch_observed")
    after = await repo.get_by_id("card")
    assert after.completion_context == before.completion_context
    assert after.completion_generation == before.completion_generation
    assert "review_dispatch_observed" in (await repo.get_card_history("card"))[0]
    await repo.update_status("card", CardStatus.DONE, completion_request=result.request)
    assert len(await repo.get_card_history("card")) == 2
