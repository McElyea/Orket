"""Final writes use retained acceptance, current scope and real SQLite transactions."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.core.contracts.card_completion_commit import CardCompletionReceipt, CardCompletionRejected
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, completion_definition, write_completion_source

pytestmark = pytest.mark.integration


async def _attempt(tmp_path, *, source=None, no_plan=False, empty=False):
    repo, service = completion_components(tmp_path / "cards.sqlite3", tmp_path / "workspace")
    params = {} if no_plan else {"completion_acceptance": completion_definition().model_dump(mode="json")}
    await repo.save(IssueRecord(id="card-1", seat="developer", summary="Increment a JSON integer", build_id="build-1",
                                session_id="session-1", status=CardStatus.CODE_REVIEW, params=params))
    if not empty:
        if source is None:
            await write_completion_source(service.workspace_root)
        else:
            await write_completion_source(service.workspace_root, source)
    context = await service.begin_attempt(repo, card_id="card-1", run_id="run-1", attempt_id="attempt-1")
    result = await service.evaluate_attempt(repo, context)
    return repo, service, context, result


async def _counts(repo):
    async with aiosqlite.connect(repo.db_path) as conn:
        cursor = await conn.execute("SELECT (SELECT count(*) FROM card_completion_commits), "
                                    "(SELECT count(*) FROM card_transactions)")
        return tuple(await cursor.fetchone())


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [CardStatus.DONE, CardStatus.GUARD_APPROVED])
# Layer: integration
async def test_completion_persists_bound_receipt_and_idempotent_history(tmp_path, status):
    repo, service, context, result = await _attempt(tmp_path)
    assert result.decision.sufficient
    await repo.update_status("card-1", status, completion_request=result.request)
    record = await repo.get_by_id("card-1")
    assert record.status == status and record.completion_context == context
    async with aiosqlite.connect(repo.db_path) as conn:
        row = await (await conn.execute("SELECT receipt_json FROM card_completion_commits")).fetchone()
    receipt = CardCompletionReceipt.model_validate_json(row[0])
    assert receipt.digest == record.completion_ref and receipt.request == result.request
    assert await service.acceptance.evidence_store.read(receipt.request.evidence_digest)
    await repo.update_status("card-1", status, completion_request=result.request)
    assert await _counts(repo) == (1, 1)
    record.verification["last_run"] = {"support_only": True}
    await repo.save(record)
    assert (await repo.get_by_id("card-1")).completion_ref == receipt.digest


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [
    {"no_plan": True}, {"empty": True}, {"source": "answer = 42\n"},
    {"source": 'print(\'{"answer":42}\')\n'}, {"source": "raise SystemExit(1)\n"},
])
# Layer: integration
async def test_unsupported_or_failed_behavior_cannot_persist_done(tmp_path, options):
    repo, _, _, result = await _attempt(tmp_path, **options)
    assert not result.decision.sufficient
    with pytest.raises(CardCompletionRejected):
        await repo.update_status("card-1", CardStatus.DONE, completion_request=result.request)
    assert (await repo.get_by_id("card-1")).status == CardStatus.CODE_REVIEW
    assert await _counts(repo) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("bypass", ["unconfigured", "no_request", "dict_request", "save", "new_terminal", "wrong_assignee"])
# Layer: integration
async def test_alternate_repository_entrypoints_do_not_bypass_completion(tmp_path, bypass):
    repo, _, _, result = await _attempt(tmp_path)
    record = await repo.get_by_id("card-1")
    with pytest.raises(CardCompletionRejected):
        if bypass == "unconfigured":
            await AsyncCardRepository(repo.db_path).update_status("card-1", CardStatus.DONE, completion_request=result.request)
        elif bypass in {"save", "new_terminal"}:
            record.status = CardStatus.DONE
            if bypass == "new_terminal":
                record.id = "forged-card"
            await repo.save(record)
        else:
            request = result.request.model_dump() if bypass == "dict_request" else None if bypass == "no_request" else result.request
            await repo.update_status("card-1", CardStatus.DONE, assignee="other" if bypass == "wrong_assignee" else None,
                                     completion_request=request)
    assert (await repo.get_by_id("card-1")).status == CardStatus.CODE_REVIEW
    assert await _counts(repo) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["artifact", "input", "definition", "attempt", "run", "reset", "archive"])
# Layer: integration
async def test_changed_artifacts_inputs_and_attempts_reject_retained_success(tmp_path, change):
    repo, service, _, result = await _attempt(tmp_path)
    if change == "artifact":
        await write_completion_source(service.workspace_root, "print('{}')\n")
    elif change in {"input", "definition"}:
        record = await repo.get_by_id("card-1")
        if change == "input":
            record.summary = "A different objective"
        else:
            record.params["completion_acceptance"]["policy_ref"] = "different-policy.v2"
        await repo.save(record)
    elif change in {"attempt", "run"}:
        await service.begin_attempt(repo, card_id="card-1", run_id="run-2" if change == "run" else "run-1",
                                    attempt_id="attempt-2" if change == "attempt" else "attempt-1")
    elif change == "reset":
        await repo.reset_build("build-1")
    else:
        await repo.archive_card("card-1")
    with pytest.raises(CardCompletionRejected):
        await repo.update_status("card-1", CardStatus.DONE, completion_request=result.request)
    assert (await repo.get_by_id("card-1")).status != CardStatus.DONE
    assert (await _counts(repo))[0] == 0


@pytest.mark.asyncio
# Layer: integration
async def test_two_repository_instances_commit_one_receipt_and_history(tmp_path):
    repo, service, _, result = await _attempt(tmp_path)
    other = AsyncCardRepository(repo.db_path, completion_authority=service)
    await asyncio.gather(*(candidate.update_status("card-1", CardStatus.DONE, completion_request=result.request)
                           for candidate in (repo, other)))
    assert (await other.get_by_id("card-1")).status == CardStatus.DONE
    assert await _counts(repo) == (1, 1)


@pytest.mark.asyncio
# Layer: integration
async def test_attempt_binding_is_compare_and_swap_and_caller_save_cannot_restore_it(tmp_path):
    repo, service, context, result = await _attempt(tmp_path)
    with pytest.raises(CardCompletionRejected, match="ATTEMPT_STALE"):
        await repo.begin_completion_attempt(context)
    stale = await repo.get_by_id("card-1")
    next_context = await service.begin_attempt(repo, card_id="card-1", run_id="run-2", attempt_id="attempt-2")
    await repo.save(stale)
    assert (await repo.get_by_id("card-1")).completion_context == next_context
    with pytest.raises(CardCompletionRejected, match="CONTEXT_STALE"):
        await repo.update_status("card-1", CardStatus.DONE, completion_request=result.request)


@pytest.mark.asyncio
# Layer: integration
async def test_missing_evidence_cannot_commit_and_reader_does_not_repair_it(tmp_path):
    repo, service, _, result = await _attempt(tmp_path)
    request = result.request.model_copy(update={"evidence_digest": "0" * 64})
    with pytest.raises(CardCompletionRejected, match="ACCEPTANCE_REQUIRED") as rejected:
        await repo.update_status("card-1", CardStatus.DONE, completion_request=request)
    assert "retained_evidence_unverifiable" in rejected.value.decision.diagnostics[0]
    assert await service.acceptance.evidence_store.read("0" * 64) is None
    assert await _counts(repo) == (0, 0)


@pytest.mark.asyncio
# Layer: integration
async def test_direct_sql_backstops_and_bulk_invalidation(tmp_path):
    repo, _, context, _ = await _attempt(tmp_path)
    async with aiosqlite.connect(repo.db_path) as conn:
        for statement in ("UPDATE issues SET status='done' WHERE id='card-1'",
                          "UPDATE issues SET status='guard_approved' WHERE id='card-1'",
                          "DELETE FROM issues WHERE id='card-1'",
                          "UPDATE issues SET id='replacement' WHERE id='card-1'"):
            with pytest.raises(aiosqlite.IntegrityError):
                await conn.execute(statement)
        await conn.execute("UPDATE issues SET params_json=? WHERE id='card-1'", (json.dumps({"new": "input"}),))
        await conn.commit()
    changed = await repo.get_by_id("card-1")
    assert changed.completion_context is None and changed.completion_generation == context.generation + 1
