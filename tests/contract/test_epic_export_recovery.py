"""Layer: contract. Real SQLite ownership with an explicitly simulated export callback."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.application.services.epic_preparation_service import EpicPreparationService
from orket.core.contracts.epic_export_recovery import EpicExportRecoveryRequest
from orket.core.domain.outward_authorization import args_hash
from tests.helpers.epic_export_recovery import recovery_request
from tests.helpers.epic_publication_recovery_worker import configure_local_export_probe
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]
SESSION = "export-recovery-session"


async def run(pipeline, request=None):
    return await pipeline.run_card("publication_epic", build_id="build", session_id=SESSION, export_recovery=request)


async def pending_export(root, workspace, db, monkeypatch):
    monkeypatch.setenv("ORKET_GITEA_ARTIFACT_EXPORT", "1")
    pipeline = await publication_pipeline(root, workspace, db)
    configure_local_export_probe(pipeline.artifact_exporter)
    calls = []

    async def workload(**_kwargs):
        calls.append("workload")
        await accept_publication_card(pipeline, workspace)

    async def lost_export(**_kwargs):
        calls.append("initial-export")
        raise OSError("fixture export reply unavailable")

    pipeline.orchestrator.execute_epic = workload
    pipeline.artifact_exporter.export_run = lost_export
    observed = await run(pipeline)
    assert observed.observation == "unresolved" and "fixture export reply unavailable" in observed.reason
    async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
        preparation = await transaction.get_preparation()
        owner = await transaction.export_dispatch.get()
    assert preparation.phase == 4 and owner.phase == "claimed"
    return pipeline, preparation, owner, calls


def successful_export(pipeline, calls):
    async def export(**kwargs):
        calls.append("retry-export")
        intent = kwargs["export_intent"]
        return {"commit": intent.commit, "tree": intent.tree}

    pipeline.artifact_exporter.export_run = export


# Layer: contract
async def test_explicit_export_retry_preserves_workload_intent_and_reentry_grant(test_root, workspace, db_path, monkeypatch):
    pipeline, preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    try:
        acceptance = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        assert not (await run(pipeline)).succeeded
        successful_export(pipeline, calls)
        request = recovery_request(owner)
        first = await run(pipeline, request)
        assert first.succeeded and (await run(pipeline, request)).succeeded
        assert calls == ["workload", "initial-export", "retry-export"]
        assert await pipeline.async_cards.read_completion_receipt("ISSUE-1") == acceptance
        async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
            retained = await transaction.get_preparation()
            current = await transaction.export_dispatch.get()
            published = await transaction.get()
        assert retained.export_intent == preparation.export_intent and current.phase == "settled"
        assert current.origin_ref() == owner.origin_ref() and current.fencing_generation == 2
        assert current.recoveries[0].request.model_dump(mode="json") == request
        assert published.plan.ledger["artifacts"]["epic_export_dispatch"] == current.claim_ref()
    finally:
        await pipeline.close()


# Layer: contract
async def test_confirmed_export_recovery_records_request_without_retry(test_root, workspace, db_path, monkeypatch):
    pipeline, preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)

    async def confirmed(intent):
        assert intent == preparation.export_intent
        return {"commit": intent.commit, "tree": intent.tree}

    pipeline.artifact_exporter.reconcile_export = confirmed
    try:
        assert (await run(pipeline, recovery_request(owner))).succeeded
        assert calls == ["workload", "initial-export"]
    finally:
        await pipeline.close()


@pytest.mark.parametrize("field", ["expected_owner_id", "expected_claim_digest", "expected_fencing_generation",
                                    "expected_intent_digest"])
# Layer: contract
async def test_stale_export_recovery_cannot_dispatch(test_root, workspace, db_path, monkeypatch, field):
    pipeline, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    request = recovery_request(owner)
    request[field] = 5 if field == "expected_fencing_generation" else "f" * 64
    try:
        observed = await run(pipeline, request)
        assert not observed.succeeded and "CONFLICT" in observed.reason
        assert calls == ["workload", "initial-export"]
        async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
            assert await transaction.export_dispatch.get() == owner
    finally:
        await pipeline.close()


# Layer: contract
async def test_concurrent_identical_export_recovery_has_one_local_dispatch_grant(test_root, workspace, db_path, monkeypatch):
    first, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    second = await publication_pipeline(test_root, workspace, db_path)
    configure_local_export_probe(second.artifact_exporter)
    for pipeline in (first, second):
        successful_export(pipeline, calls)
    try:
        results = await asyncio.gather(run(first, recovery_request(owner)), run(second, recovery_request(owner)))
        assert any(result.succeeded for result in results)
        assert calls == ["workload", "initial-export", "retry-export"]
        for result in results:
            assert result.succeeded or "E_EPIC_EXPORT_OUTCOME_UNCERTAIN" in result.reason
    finally:
        await first.close()
        await second.close()


# Layer: contract
async def test_superseded_export_caller_cannot_dispatch_after_new_owner(test_root, workspace, db_path, monkeypatch):
    first, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    second = await publication_pipeline(test_root, workspace, db_path)
    configure_local_export_probe(second.artifact_exporter)
    original_finish = EpicPreparationService._finish
    entered, release = asyncio.Event(), asyncio.Event()

    async def held_finish(service, *args, **kwargs):
        if kwargs.get("export_owner") is not None and kwargs["export_owner"].fencing_generation == 2:
            entered.set()
            await release.wait()
        return await original_finish(service, *args, **kwargs)

    monkeypatch.setattr(EpicPreparationService, "_finish", held_finish)
    successful_export(first, calls)
    successful_export(second, calls)
    task = asyncio.create_task(run(first, recovery_request(owner)))
    try:
        await asyncio.wait_for(entered.wait(), 10)
        async with second.epic_publication.repository.transaction(SESSION) as transaction:
            intermediate = await transaction.export_dispatch.get()
        assert (await run(second, recovery_request(intermediate, "recovery-2"))).succeeded
        release.set()
        result = await asyncio.wait_for(task, 10)
        assert result.succeeded or "E_EPIC_EXPORT_FENCE_CONFLICT" in result.reason
        assert calls == ["workload", "initial-export", "retry-export"]
        repeated = await run(first, recovery_request(owner))
        assert not repeated.succeeded and "E_EPIC_EXPORT_RECOVERY_SUPERSEDED" in repeated.reason
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()


@pytest.mark.parametrize("damage", ["deleted", "digest", "history"])
# Layer: contract
async def test_export_owner_damage_does_not_fall_back_to_legacy_confirmation(test_root, workspace, db_path, monkeypatch, damage):
    pipeline, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    try:
        async with aiosqlite.connect(pipeline.epic_publication.repository.db_path) as connection:
            if damage == "deleted":
                await connection.execute("DELETE FROM epic_export_dispatches")
            else:
                payload = owner.model_dump(mode="json")
                if damage == "history":
                    payload["fencing_generation"] = 2
                await connection.execute("UPDATE epic_export_dispatches SET payload = ?, digest = ?",
                                         (json.dumps(payload), "0" * 64 if damage == "digest" else args_hash(payload)))
            await connection.commit()
        for request in (None, recovery_request(owner)):
            observed = await run(pipeline, request)
            assert observed.observation == "unresolved" and not observed.succeeded
        assert calls == ["workload", "initial-export"]
        assert await pipeline.success.get(SESSION) is None
    finally:
        await pipeline.close()


# Layer: contract
async def test_lost_retry_result_requires_new_explicit_request(test_root, workspace, db_path, monkeypatch):
    pipeline, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    try:
        request = recovery_request(owner)
        assert not (await run(pipeline, request)).succeeded
        assert not (await run(pipeline, request)).succeeded
        assert calls == ["workload", "initial-export", "initial-export"]
        async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
            current = await transaction.export_dispatch.get()
        successful_export(pipeline, calls)
        assert (await run(pipeline, recovery_request(current, "recovery-2"))).succeeded
        conflict = {**recovery_request(current, "recovery-2"), "operator_ref": "operator:other"}
        observed = await run(pipeline, conflict)
        assert not observed.succeeded and "E_EPIC_EXPORT_RECOVERY_REQUEST_CONFLICT" in observed.reason
        assert calls == ["workload", "initial-export", "initial-export", "retry-export"]
    finally:
        await pipeline.close()


@pytest.mark.parametrize("change", [{"resolution": "force_push"}, {"expected_fencing_generation": "1"},
                                   {"schema_version": "unknown"}])
# Layer: contract
async def test_export_recovery_request_rejects_unsupported_authority(change):
    request = {"session_id": SESSION, "request_id": "r", "expected_owner_id": "owner",
               "expected_fencing_generation": 1, "expected_claim_digest": "0" * 64,
               "expected_intent_digest": "1" * 64, "operator_ref": "operator", "reason_ref": "reason",
               "resolution": "retry_exact_commit", **change}
    with pytest.raises(ValueError):
        EpicExportRecoveryRequest.model_validate(request)


# Layer: contract
async def test_legacy_unmarked_preparation_can_confirm_but_cannot_gain_retry_owner(test_root, workspace, db_path, monkeypatch):
    pipeline, preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    try:
        # Construct an old-format fixture, not a migration of retained production history.
        payload = preparation.model_dump(mode="json")
        payload["artifacts"].pop("epic_export_dispatch")
        async with aiosqlite.connect(pipeline.epic_publication.repository.db_path) as connection:
            await connection.execute("DELETE FROM epic_export_dispatches")
            await connection.execute("UPDATE epic_preparations SET payload = ?, digest = ?",
                                     (json.dumps(payload), args_hash(payload)))
            await connection.commit()
        observed = await run(pipeline, recovery_request(owner))
        assert not observed.succeeded and "E_EPIC_EXPORT_RECOVERY_OWNER_MISSING" in observed.reason

        async def confirmed(intent):
            return {"commit": intent.commit, "tree": intent.tree}

        pipeline.artifact_exporter.reconcile_export = confirmed
        assert (await run(pipeline)).succeeded
        assert calls == ["workload", "initial-export"]
        async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
            assert await transaction.export_dispatch.get() is None
    finally:
        await pipeline.close()


# Layer: contract
async def test_published_export_reentry_requires_retained_owner_reference(test_root, workspace, db_path, monkeypatch):
    pipeline, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    successful_export(pipeline, calls)
    try:
        assert (await run(pipeline, recovery_request(owner))).succeeded
        async with pipeline.epic_publication.repository.transaction(SESSION) as transaction:
            published = await transaction.get()
        payload = published.model_dump(mode="json")
        payload["plan"]["ledger"]["artifacts"].pop("epic_export_dispatch")
        async with aiosqlite.connect(pipeline.epic_publication.repository.db_path) as connection:
            await connection.execute("UPDATE epic_publications SET payload = ?, digest = ?",
                                     (json.dumps(payload), args_hash(payload)))
            await connection.commit()
        observed = await run(pipeline)
        assert not observed.succeeded and "E_EPIC_EXPORT_PUBLICATION_OWNER_CONFLICT" in observed.reason
        assert calls == ["workload", "initial-export", "retry-export"]
    finally:
        await pipeline.close()


@pytest.mark.parametrize("invalid", ["session", "target", "both"])
# Layer: contract
async def test_public_export_recovery_requires_one_bound_epic_operation(test_root, workspace, db_path, monkeypatch, invalid):
    pipeline, _preparation, owner, calls = await pending_export(test_root, workspace, db_path, monkeypatch)
    kwargs = {"build_id": "build", "session_id": SESSION, "export_recovery": recovery_request(owner)}
    target = "publication_epic"
    if invalid == "session":
        kwargs["session_id"] = "another-session"
    if invalid == "target":
        target = "ISSUE-1"
    if invalid == "both":
        kwargs["admission_recovery"] = {}
    try:
        with pytest.raises(ValueError, match="RECOVERY"):
            await pipeline.run_card(target, **kwargs)
        assert calls == ["workload", "initial-export"]
    finally:
        await pipeline.close()
