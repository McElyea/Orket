"""Standard epic admission excludes competing writers before initialization."""
from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from orket.runtime.execution.epic_run_orchestrator import EpicRunOrchestrator
from tests.helpers.card_completion import complete_existing_card
from tests.integration.test_epic_closeout_process import read_barrier
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_epic_publication_recovery_process import launch, retained_rows

pytestmark = pytest.mark.integration


def hold_initialization(pipeline, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    original = EpicRunOrchestrator._ensure_session_and_cards

    async def pause_owner(runner, setup):
        if runner.orchestrator is pipeline.orchestrator:
            entered.set()
            await release.wait()
        return await original(runner, setup)

    monkeypatch.setattr(EpicRunOrchestrator, "_ensure_session_and_cards", pause_owner)
    return entered, release


@pytest.mark.asyncio
@pytest.mark.parametrize("second_session", ["owner", "competitor"])
# Layer: integration
async def test_initial_admission_reserves_shared_resources_before_card_writes(
    test_root, workspace, db_path, monkeypatch, second_session,
):
    first = await publication_pipeline(test_root, workspace, db_path)
    second = await publication_pipeline(test_root, workspace, db_path)
    entered, release = hold_initialization(first, monkeypatch)
    calls = []

    async def execute_owner(**_kwargs):
        calls.append("owner")
        await accept_publication_card(first, workspace)

    async def execute_competitor(**_kwargs):
        calls.append("competitor")
        await accept_publication_card(second, workspace)

    first.orchestrator.execute_epic = execute_owner
    second.orchestrator.execute_epic = execute_competitor
    task = asyncio.create_task(first.run_epic("publication_epic", build_id="build", session_id="owner"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=15)
        if second_session == "competitor":
            with pytest.raises(ValueError, match="E_EPIC_ADMISSION_"):
                await second.run_epic("publication_epic", build_id="build", session_id=second_session)
        else:
            observed = await second.run_epic("publication_epic", build_id="build", session_id=second_session)
            assert observed.observation == "unresolved" and not observed.succeeded
            assert "E_EPIC_ADMISSION_" in observed.reason
        assert calls == []
        assert await first.async_cards.get_by_build("build") == []
        assert await second.sessions.get_session("competitor") is None
        release.set()
        await asyncio.wait_for(task, timeout=30)
        assert calls == ["owner"]
        assert (await first.run_ledger.get_run("owner"))["status"] == "done"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", ["workspace", "build", "card", None])
# Layer: integration
async def test_admission_excludes_each_shared_resource_and_allows_disjoint_work(
    test_root, workspace, db_path, monkeypatch, shared,
):
    first = await publication_pipeline(test_root, workspace, db_path)
    other_workspace = workspace if shared == "workspace" else test_root / "other-workspace"
    second = await publication_pipeline(test_root, other_workspace, db_path)
    epic_path = test_root / "model/core/epics/publication_epic.json"
    epic = json.loads(await asyncio.to_thread(epic_path.read_text, encoding="utf-8"))
    epic.update(id="other_epic", name="other_epic")
    card_id = "ISSUE-1" if shared == "card" else "ISSUE-2"
    epic["issues"][0]["id"] = card_id
    await asyncio.to_thread(epic_path.with_name("other_epic.json").write_text, json.dumps(epic), encoding="utf-8")
    entered, release = hold_initialization(first, monkeypatch)

    async def execute_owner(**_kwargs):
        await accept_publication_card(first, workspace)

    async def execute_other(**_kwargs):
        await complete_existing_card(second.async_cards, card_id, other_workspace,
                                     service=second.runtime_context.card_completion)

    first.orchestrator.execute_epic, second.orchestrator.execute_epic = execute_owner, execute_other
    task = asyncio.create_task(first.run_epic("publication_epic", build_id="build", session_id="owner"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=15)
        arguments = {"build_id": "build" if shared == "build" else "other-build", "session_id": "other"}
        if shared:
            with pytest.raises(ValueError, match="E_EPIC_ADMISSION_RESOURCE_BUSY:owner"):
                await second.run_epic("other_epic", **arguments)
            assert await second.async_cards.get_by_id(card_id) is None
            assert await second.sessions.get_session("other") is None
        else:
            await second.run_epic("other_epic", **arguments)
            assert (await second.run_ledger.get_run("other"))["status"] == "done"
        release.set()
        await asyncio.wait_for(task, timeout=30)
        assert (await first.run_ledger.get_run("owner"))["status"] == "done"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing", "digest", "early_release"])
# Layer: integration
async def test_admission_evidence_damage_cannot_publish_or_release(test_root, workspace, db_path, damage):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    repository = pipeline.epic_publication.repository

    async def execute_fixture(**_kwargs):
        await accept_publication_card(pipeline, workspace)
        if damage == "early_release":
            async with repository.transaction("owner") as transaction:
                record = await transaction.get_admission()
                await transaction.save_admission(record.model_copy(update={"phase": "released"}))
        else:
            async with aiosqlite.connect(repository.db_path) as connection:
                sql = ("DELETE FROM epic_run_admissions" if damage == "missing" else
                       "UPDATE epic_run_admissions SET digest = 'damaged'")
                await connection.execute(sql)
                await connection.commit()

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        if damage == "missing":
            with pytest.raises(ValueError, match="E_EPIC_ADMISSION_"):
                await pipeline.run_epic("publication_epic", build_id="build", session_id="owner")
        else:
            observed = await pipeline.run_epic("publication_epic", build_id="build", session_id="owner")
            assert observed.observation == "unresolved" and not observed.succeeded
            assert "E_EPIC_ADMISSION_" in observed.reason
        assert (await pipeline.run_ledger.get_run("owner"))["status"] == "running"
        assert (await pipeline.sessions.get_session("owner"))["status"] == "Started"
        assert await pipeline.success.get("owner") is None
        receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        if damage == "missing":
            with pytest.raises(ValueError, match="E_EPIC_ADMISSION_"):
                await pipeline.run_epic("publication_epic", build_id="build", session_id="owner")
        else:
            observed = await pipeline.run_epic("publication_epic", build_id="build", session_id="owner")
            assert observed.observation == "unresolved" and not observed.succeeded
            assert "E_EPIC_ADMISSION_" in observed.reason
        assert await pipeline.async_cards.read_completion_receipt("ISSUE-1") == receipt
    finally:
        await pipeline.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("lose_publication", [False, True])
# Layer: integration
async def test_verified_publication_releases_resources_with_retained_history(
    test_root, workspace, db_path, lose_publication,
):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    calls = []

    async def execute_fixture(**kwargs):
        calls.append(kwargs["run_id"])
        await accept_publication_card(pipeline, workspace)

    pipeline.orchestrator.execute_epic = execute_fixture
    try:
        await pipeline.run_epic("publication_epic", build_id="build", session_id="owner")
        async with pipeline.epic_publication.repository.transaction("owner") as transaction:
            original = await transaction.get_admission()
            assert original.phase == "released"
        if lose_publication:
            async with aiosqlite.connect(pipeline.epic_publication.repository.db_path) as connection:
                await connection.execute("DELETE FROM epic_publications")
                await connection.commit()
            with pytest.raises(ValueError, match="E_EPIC_ADMISSION_RELEASE_UNCONFIRMED"):
                await pipeline.run_epic("publication_epic", build_id="build", session_id="next")
            assert calls == ["owner"]
        else:
            await pipeline.run_epic("publication_epic", build_id="build", session_id="next")
            assert calls == ["owner", "next"]
            assert (await pipeline.run_ledger.get_run("next"))["status"] == "done"
        async with pipeline.epic_publication.repository.transaction("owner") as transaction:
            assert await transaction.get_admission() == original
    finally:
        await pipeline.close()


@pytest.mark.asyncio
# Layer: integration
async def test_native_admission_survives_owner_death_before_run_ledger(test_root, workspace, db_path):
    child = await launch(test_root, workspace, db_path, "kill", "admission")
    observers = []
    try:
        await asyncio.wait_for(read_barrier(child), timeout=30)
        before = await retained_rows(db_path)
        assert all(not rows for rows in before.values())
        journal = test_root / "orket_test.db.epic-publications.sqlite3"
        journal_bytes = await asyncio.to_thread(journal.read_bytes)
        observers.append(await launch(test_root, workspace, db_path, "resume", "admission"))
        _, stderr = await asyncio.wait_for(observers[-1].communicate(), timeout=30)
        assert observers[-1].returncode != 0 and "E_EPIC_ADMISSION_OUTCOME_UNCERTAIN" in stderr.decode()
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
        observers.extend([await launch(test_root, workspace, db_path, "resume", "admission") for _ in range(2)])
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in observers[1:])), timeout=40)
        for process, (_stdout, stderr) in zip(observers[1:], replies, strict=True):
            assert process.returncode != 0 and "E_EPIC_ADMISSION_OUTCOME_UNCERTAIN" in stderr.decode()
        assert await retained_rows(db_path) == before
        assert await asyncio.to_thread(journal.read_bytes) == journal_bytes
    finally:
        for process in [child, *observers]:
            if process.returncode is None:
                process.kill()
            await process.communicate()
