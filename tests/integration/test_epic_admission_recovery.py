"""Explicit pre-initialization recovery fences the original runtime owner."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.application.services.epic_admission_service import EpicAdmissionService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.epic_publication import EpicAdmissionRecoveryRequest
from orket.core.domain.outward_authorization import args_hash
from tests.integration.test_epic_closeout_process import read_barrier
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_epic_publication_recovery_process import launch, retained_rows
from tests.integration.test_epic_run_admission import hold_initialization

pytestmark = pytest.mark.integration


def recovery_request(admission, *, request_id="recovery-1"):
    return {"schema_version": "epic_admission_recovery_request.v1", "session_id": admission.session_id,
            "request_id": request_id, "expected_owner_id": admission.owner_id,
            "expected_fencing_generation": admission.fencing_generation, "expected_claim_digest": admission.claim_ref()["digest"],
            "operator_ref": "operator:fixture", "reason_ref": "evidence:paused-before-initialization"}


@pytest.mark.asyncio
# Layer: integration
async def test_explicit_recovery_completes_and_fences_paused_original_owner(test_root, workspace, db_path, monkeypatch):
    first = await publication_pipeline(test_root, workspace, db_path)
    recovered = await publication_pipeline(test_root, workspace, db_path)
    entered, release = asyncio.Event(), asyncio.Event()
    original = EpicAdmissionService.claim
    original_claim = []
    calls = []

    async def pause_claim(service, *args, **kwargs):
        claim = await original(service, *args, **kwargs)
        original_claim.append(claim)
        entered.set()
        await release.wait()
        return claim

    async def original_work(**_kwargs):
        calls.append("stale-owner")

    async def recovered_work(**_kwargs):
        calls.append("replacement")
        await accept_publication_card(recovered, workspace)

    monkeypatch.setattr(EpicAdmissionService, "claim", pause_claim)
    first.orchestrator.execute_epic, recovered.orchestrator.execute_epic = original_work, recovered_work
    task = asyncio.create_task(first.run_card("publication_epic", build_id="build", session_id="owner"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=15)
        request = recovery_request(original_claim[0])
        await recovered.run_card("publication_epic", build_id="build", session_id="owner", admission_recovery=request)
        async with recovered.epic_publication.repository.transaction("owner") as transaction:
            current = await transaction.get_admission()
            assert current.fencing_generation == 2 and current.phase == "released"
            assert current.owner_id != original_claim[0].owner_id
            assert current.recoveries[0].request.model_dump(mode="json") == request
        release.set()
        observed = await asyncio.wait_for(task, timeout=15)
        assert observed.observation == "unresolved" and not observed.succeeded
        assert "E_EPIC_ADMISSION_FENCE_CONFLICT" in observed.reason
        assert calls == ["replacement"]
        assert (await recovered.run_ledger.get_run("owner"))["status"] == "done"
        await recovered.run_card("publication_epic", build_id="build", session_id="owner", admission_recovery=request)
        assert calls == ["replacement"]
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await recovered.close()


async def abandon_claim(pipeline, monkeypatch):
    original = EpicAdmissionService.claim

    async def interrupt_after_claim(service, *args, **kwargs):
        await original(service, *args, **kwargs)
        raise asyncio.CancelledError

    with monkeypatch.context() as patch:
        patch.setattr(EpicAdmissionService, "claim", interrupt_after_claim)
        with pytest.raises(asyncio.CancelledError):
            await pipeline.run_card("publication_epic", build_id="build", session_id="owner")
    async with pipeline.epic_publication.repository.transaction("owner") as transaction:
        return await transaction.get_admission()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["owner", "digest", "generation", "request_id", "operator", "history", "legacy"])
# Layer: integration
async def test_recovery_refuses_stale_conflicting_or_damaged_authority(test_root, workspace, db_path, monkeypatch, changed):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    try:
        original = await abandon_claim(pipeline, monkeypatch)
        request = recovery_request(original)
        inputs = RuntimeInputService()
        service = EpicAdmissionService(pipeline.epic_publication.repository, owner_id=inputs.create_effect_owner_id,
                                       now=inputs.utc_now_iso)
        replacement = await service.recover_claim("owner", original.request, original.export_binding,
                                                   EpicAdmissionRecoveryRequest.model_validate(request))
        if changed in {"history", "legacy"}:
            payload = replacement.model_dump(mode="json")
            if changed == "history":
                payload["recoveries"][0]["action"]["actor_ref"] = "operator:substituted"
            else:
                payload["schema_version"] = "epic_run_admission.v1"
            async with aiosqlite.connect(pipeline.epic_publication.repository.db_path) as connection:
                await connection.execute("UPDATE epic_run_admissions SET payload = ?, digest = ? WHERE session_id = ?",
                                         (json.dumps(payload), args_hash(payload), "owner"))
                await connection.commit()
        else:
            changes = {"owner": {"expected_owner_id": "stale"}, "digest": {"expected_claim_digest": "0" * 64},
                       "generation": {"expected_fencing_generation": 99}, "request_id": {"request_id": "new-request"},
                       "operator": {"operator_ref": "operator:different"}}
            request.update(changes[changed])
        journal = pipeline.epic_publication.repository.db_path
        before = await asyncio.to_thread(journal.read_bytes)
        observed = await pipeline.run_card("publication_epic", build_id="build", session_id="owner", admission_recovery=request)
        assert observed.observation == "unresolved" and not observed.succeeded
        assert observed.reason
        assert await asyncio.to_thread(journal.read_bytes) == before
        assert await pipeline.sessions.get_session("owner") is None
        assert await pipeline.async_cards.get_by_build("build") == []
    finally:
        await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_recovery_refuses_after_initialization_marker_without_a_ledger(test_root, workspace, db_path, monkeypatch):
    first = await publication_pipeline(test_root, workspace, db_path)
    other = await publication_pipeline(test_root, workspace, db_path)
    entered, release = hold_initialization(first, monkeypatch)

    async def execute_fixture(**_kwargs):
        await accept_publication_card(first, workspace)

    first.orchestrator.execute_epic = execute_fixture
    task = asyncio.create_task(first.run_card("publication_epic", build_id="build", session_id="owner"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=15)
        async with first.epic_publication.repository.transaction("owner") as transaction:
            admission = await transaction.get_admission()
        assert admission.initialization_started and await first.run_ledger.get_run("owner") is None
        observed = await other.run_card("publication_epic", build_id="build", session_id="owner",
                                        admission_recovery=recovery_request(admission))
        assert observed.observation == "unresolved" and not observed.succeeded
        assert "E_EPIC_ADMISSION_RECOVERY_REQUIRES_PRE_INITIALIZATION" in observed.reason
        release.set()
        await asyncio.wait_for(task, timeout=30)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await other.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("old_owner", ["killed", "resumed"])
# Layer: integration
async def test_native_owner_death_and_concurrent_recovery_dispatch_once(test_root, workspace, db_path, old_owner):
    child = await launch(test_root, workspace, db_path, "kill" if old_owner == "killed" else "stale", "admission")
    resumed = []
    pipeline = None
    try:
        await asyncio.wait_for(read_barrier(child), timeout=30)
        pipeline = await publication_pipeline(test_root, workspace, db_path)
        async with pipeline.epic_publication.repository.transaction("publication-session") as transaction:
            admission = await transaction.get_admission()
        assert not admission.initialization_started
        request = recovery_request(admission)
        if old_owner == "killed":
            child.kill()
            await asyncio.wait_for(child.communicate(), timeout=10)
        resumed = [await launch(test_root, workspace, db_path, "recover", "admission", recovery=request) for _ in range(2)]
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=50)
        assert any(p.returncode == 0 for p in resumed)
        for process, (_stdout, stderr) in zip(resumed, replies, strict=True):
            if process.returncode:
                assert any(error in stderr.decode() for error in (
                    "E_EPIC_ADMISSION_INITIALIZATION_UNCERTAIN", "E_EPIC_ADMISSION_FENCE_CONFLICT",
                    "E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN"))
        marker = await asyncio.to_thread((workspace / "native-recovery-dispatch.log").read_text, encoding="utf-8")
        assert marker.splitlines() == ["dispatch"]
        rows = await retained_rows(db_path)
        assert len(rows["run_ledger"]) == len(rows["sessions"]) == len(rows["success_ledger"]) == 1
        assert rows["run_ledger"][0]["status"] == "done"
        if old_owner == "resumed":
            _, stderr = await asyncio.wait_for(child.communicate(b"continue\n"), timeout=20)
            assert child.returncode != 0 and "E_EPIC_ADMISSION_FENCE_CONFLICT" in stderr.decode()
            assert await retained_rows(db_path) == rows
            assert (await asyncio.to_thread((workspace / "native-recovery-dispatch.log").read_text, encoding="utf-8")).splitlines() == ["dispatch"]
        async with pipeline.epic_publication.repository.transaction("publication-session") as transaction:
            current = await transaction.get_admission()
        assert current.fencing_generation == 2 and len(current.recoveries) == 1 and current.phase == "released"
    finally:
        for process in [child, *resumed]:
            if process.returncode is None:
                process.kill()
            await process.communicate()
        if pipeline is not None:
            await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_successive_recoveries_preserve_history_and_reject_superseded_requests(test_root, workspace, db_path, monkeypatch):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    calls = []

    async def execute_fixture(**_kwargs):
        calls.append("dispatch")
        await accept_publication_card(pipeline, workspace)

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        original = await abandon_claim(pipeline, monkeypatch)
        inputs = RuntimeInputService()
        service = EpicAdmissionService(pipeline.epic_publication.repository, owner_id=inputs.create_effect_owner_id,
                                       now=inputs.utc_now_iso)
        first_request = recovery_request(original)
        first = await service.recover_claim("owner", original.request, original.export_binding,
                                            EpicAdmissionRecoveryRequest.model_validate(first_request))
        last_request = recovery_request(first, request_id="recovery-2")
        current = await service.recover_claim("owner", original.request, original.export_binding,
                                              EpicAdmissionRecoveryRequest.model_validate(last_request))
        assert current.fencing_generation == 3 and len(current.recoveries) == 2
        with pytest.raises(ValueError, match="E_EPIC_ADMISSION_FENCE_CONFLICT"):
            await service.begin_initialization(first)
        observed = await pipeline.run_card("publication_epic", build_id="build", session_id="owner", admission_recovery=first_request)
        assert observed.observation == "unresolved" and not observed.succeeded
        assert "E_EPIC_ADMISSION_RECOVERY_SUPERSEDED" in observed.reason
        assert calls == []
        for _ in range(2):
            await pipeline.run_card("publication_epic", build_id="build", session_id="owner", admission_recovery=last_request)
        assert calls == ["dispatch"]
        async with pipeline.epic_publication.repository.transaction("owner") as transaction:
            assert (await transaction.get_admission()).recoveries == current.recoveries
    finally:
        await pipeline.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["target", "session", "schema", "generation_type"])
# Layer: integration
async def test_recovery_requires_explicit_bound_epic_and_valid_request(test_root, workspace, db_path, monkeypatch, invalid):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    try:
        original = await abandon_claim(pipeline, monkeypatch)
        request = recovery_request(original)
        if invalid == "schema":
            request["schema_version"] = "unknown"
        if invalid == "generation_type":
            request["expected_fencing_generation"] = True
        with pytest.raises(ValueError):
            await pipeline.run_card("ISSUE-1" if invalid == "target" else "publication_epic", build_id="build",
                                    session_id=None if invalid == "session" else "owner", admission_recovery=request)
        async with pipeline.epic_publication.repository.transaction("owner") as transaction:
            assert await transaction.get_admission() == original
        assert await pipeline.sessions.get_session("owner") is None
    finally:
        await pipeline.close()
