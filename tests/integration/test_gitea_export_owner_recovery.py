"""Layer: integration. Native owner recovery against an owned, actual localhost Gitea."""
from __future__ import annotations

import asyncio
import os

import pytest

from orket.application.services.gitea_artifact_exporter_factory import create_gitea_artifact_exporter
from tests.helpers.epic_export_recovery import recovery_request
from tests.helpers.gitea_server import get_visible, local_gitea
from tests.integration.test_epic_closeout_process import read_barrier
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_epic_publication_recovery_process import launch

pytestmark = [pytest.mark.integration, pytest.mark.asyncio,
              pytest.mark.skipif(os.getenv("ORKET_RUN_GITEA_EXPORT_ACCEPTANCE") != "1",
                                 reason="Explicit owned localhost Gitea acceptance required")]


@pytest.mark.parametrize("old_owner", ["killed", "resumed"])
# Layer: integration
async def test_native_export_owner_recovery_fences_dispatch_and_preserves_exact_commit(test_root, workspace, db_path,
                                                                                     monkeypatch, old_owner):
    async with local_gitea() as server:
        for key, value in server.export_environment(str(test_root / "export-cache")).items():
            monkeypatch.setenv(key, value)
        child = await launch(test_root, workspace, db_path, "kill" if old_owner == "killed" else "stale", "gitea_owner")
        pipeline, resumed = None, []
        try:
            await asyncio.wait_for(read_barrier(child), 50)
            pipeline = await publication_pipeline(test_root, workspace, db_path)
            async with pipeline.epic_publication.repository.transaction("publication-session") as transaction:
                preparation = await transaction.get_preparation()
                owner = await transaction.export_dispatch.get()
                admission = await transaction.get_admission()
                outcome = await transaction.get_outcome()
            assert preparation.phase == 4 and admission.initialization_started
            assert not await asyncio.to_thread((workspace / "native-export-pushes.log").exists)
            acceptance = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
            request = recovery_request(owner, "native-export-recovery", operator_ref="operator:localhost-acceptance",
                                       reason_ref="evidence:retained-native-export-boundary")
            if old_owner == "killed":
                child.kill()
                await asyncio.wait_for(child.communicate(), 10)
            resumed = [await launch(test_root, workspace, db_path, "export_recover", "gitea_owner", export_recovery=request)
                       for _ in range(2)]
            replies = await asyncio.wait_for(asyncio.gather(*(process.communicate() for process in resumed)), 80)
            assert any(process.returncode == 0 for process in resumed)
            for process, (_stdout, stderr) in zip(resumed, replies, strict=True):
                if process.returncode:
                    assert "E_EPIC_EXPORT_OUTCOME_UNCERTAIN" in stderr.decode(errors="replace")
            if old_owner == "resumed":
                _stdout, stderr = await asyncio.wait_for(child.communicate(b"continue\n"), 30)
                assert child.returncode == 0 or "E_EPIC_EXPORT_FENCE_CONFLICT" in stderr.decode(errors="replace")
            assert (await asyncio.to_thread((workspace / "native-export-pushes.log").read_text)).splitlines() == ["push"]
            commits = await get_visible(server, "/api/v1/repos/export-proof/artifacts/commits")
            assert [row["sha"] for row in commits.json()] == [preparation.export_intent.commit]
            async with pipeline.epic_publication.repository.transaction("publication-session") as transaction:
                current = await transaction.export_dispatch.get()
                published = await transaction.get()
                assert await transaction.get_outcome() == outcome
                assert (await transaction.get_admission()).claim_ref() == admission.claim_ref()
            assert current.phase == "settled" and current.fencing_generation == 2 and len(current.recoveries) == 1
            assert published.plan.ledger["artifacts"]["gitea_export"]["commit"] == preparation.export_intent.commit
            assert await pipeline.async_cards.read_completion_receipt("ISSUE-1") == acceptance
            assert (await pipeline.run_ledger.get_run("publication-session"))["status"] == "done"
            assert (await pipeline.run_card("publication_epic", build_id="build", session_id="publication-session",
                                            export_recovery=request)).succeeded
        finally:
            for process in [child, *resumed]:
                if process.returncode is None:
                    process.kill()
                await process.communicate()
            if pipeline is not None:
                await pipeline.close()


# Layer: integration
async def test_exact_export_recovery_refuses_changed_remote_history(test_root, workspace, db_path, monkeypatch):
    async with local_gitea() as server:
        for key, value in server.export_environment(str(test_root / "export-cache")).items():
            monkeypatch.setenv(key, value)
        pipeline = await publication_pipeline(test_root, workspace, db_path)
        export = pipeline.artifact_exporter.export_run

        async def workload(**_kwargs):
            await accept_publication_card(pipeline, workspace)

        async def interrupted(**_kwargs):
            raise OSError("fixture interruption before actual push")

        pipeline.orchestrator.execute_epic = workload
        pipeline.artifact_exporter.export_run = interrupted
        try:
            first = await pipeline.run_card("publication_epic", build_id="build", session_id="conflict")
            assert not first.succeeded and "fixture interruption" in first.reason
            async with pipeline.epic_publication.repository.transaction("conflict") as transaction:
                preparation, owner = await transaction.get_preparation(), await transaction.export_dispatch.get()
            other_workspace = test_root / "unrelated-workspace"
            await asyncio.to_thread((other_workspace / "agent_output").mkdir, parents=True)
            other = await asyncio.to_thread(create_gitea_artifact_exporter, other_workspace)
            run = {"run_id": "unrelated", "run_type": "epic", "run_name": "external-fixture", "build_id": "other",
                   "session_status": "done", "summary": {}, "export_day": "2026-09-13",
                   "export_time": "2026-09-13T12:00:00+00:00"}
            other_intent = await other.prepare_export(**run)
            await other.export_run(export_intent=other_intent, **run)
            pipeline.artifact_exporter.export_run = export
            observed = await pipeline.run_card("publication_epic", build_id="build", session_id="conflict",
                                               export_recovery=recovery_request(owner))
            assert not observed.succeeded and "E_GITEA_GIT_COMMAND_FAILED:push" in observed.reason
            commits = await get_visible(server, "/api/v1/repos/export-proof/artifacts/commits")
            assert [row["sha"] for row in commits.json()] == [other_intent.commit]
            async with pipeline.epic_publication.repository.transaction("conflict") as transaction:
                assert (await transaction.get_preparation()).export_intent == preparation.export_intent
                assert (await transaction.export_dispatch.get()).phase == "claimed"
                assert await transaction.get() is None
            assert await pipeline.success.get("conflict") is None
        finally:
            await pipeline.close()
