"""Explicit localhost Gitea acceptance, including lost publication replies."""
from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest

from orket.application.services.gitea_artifact_exporter_factory import create_gitea_artifact_exporter
from tests.helpers.gitea_server import docker, get_visible, local_gitea
from tests.integration.test_epic_closeout_process import read_barrier
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline
from tests.integration.test_epic_publication_recovery_process import launch, retained_rows

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(os.getenv("ORKET_RUN_GITEA_EXPORT_ACCEPTANCE") != "1",
                                 reason="Explicit owned localhost Gitea acceptance required")]


@pytest.mark.asyncio
# Layer: integration
async def test_committed_gitea_export_recovers_without_another_push(test_root, workspace, db_path, monkeypatch):
    async with local_gitea() as server:
        for key, value in server.export_environment(str(test_root / "export-cache")).items():
            monkeypatch.setenv(key, value)
        pipeline = await publication_pipeline(test_root, workspace, db_path)
        exported = {}
        original = pipeline.artifact_exporter.export_run

        async def lost_reply(**kwargs):
            exported.update(await original(**kwargs))
            raise OSError("Gitea push reply lost before local publication")

        async def execute_fixture(**_kwargs):
            await accept_publication_card(pipeline, workspace)

        pipeline.orchestrator.execute_epic = execute_fixture
        pipeline.artifact_exporter.export_run = lost_reply
        try:
            observed = await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session")
            assert not observed.succeeded and observed.observation == "unresolved"
            assert "Gitea push reply lost" in observed.reason
            receipt = await pipeline.async_cards.read_completion_receipt("ISSUE-1")
        finally:
            await pipeline.close()
        restarted = await publication_pipeline(test_root, workspace, db_path)

        async def forbidden(**_kwargs):
            raise AssertionError("Recovery repeated workload or export dispatch")

        restarted.orchestrator.execute_epic = forbidden
        restarted.artifact_exporter.export_run = forbidden
        try:
            await restarted.run_epic("publication_epic", build_id="build", session_id="publication-session")
            assert await restarted.async_cards.read_completion_receipt("ISSUE-1") == receipt
            row = await restarted.run_ledger.get_run("publication-session")
            assert row["status"] == "done"
            assert row["artifact_json"]["gitea_export"]["commit"] == exported["commit"]
            response = await get_visible(server, "/api/v1/repos/export-proof/artifacts/commits")
            assert [item["sha"] for item in response.json()] == [exported["commit"]]
        finally:
            await restarted.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["gitea_export", "gitea_intent"])
# Layer: integration
async def test_native_gitea_restart_confirms_effect_or_preserves_uncertainty(test_root, workspace, db_path, monkeypatch, stage):
    async with local_gitea() as server:
        for key, value in server.export_environment(str(test_root / "export-cache")).items():
            monkeypatch.setenv(key, value)
        child = await launch(test_root, workspace, db_path, "kill", stage)
        resumed = []
        try:
            await asyncio.wait_for(read_barrier(child), timeout=50)
            child.kill()
            await asyncio.wait_for(child.communicate(), timeout=10)
            before = await retained_rows(db_path)
            resumed = [await launch(test_root, workspace, db_path, "resume", stage) for _ in range(2)]
            replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=50)
            for process, (stdout, stderr) in zip(resumed, replies, strict=True):
                if stage == "gitea_export":
                    assert process.returncode == 0, stderr.decode(errors="replace")
                    assert json.loads(stdout.splitlines()[-1])["status"] == "done"
                else:
                    assert process.returncode != 0
                    assert "E_EPIC_EXPORT_OUTCOME_UNCERTAIN" in stderr.decode(errors="replace")
            async with httpx.AsyncClient(auth=(server.username, server.password)) as client:
                response = await client.get(server.url + "/api/v1/repos/export-proof/artifacts/commits")
                if stage == "gitea_export":
                    response = await get_visible(server, "/api/v1/repos/export-proof/artifacts/commits")
                    assert len(response.json()) == 1
                else:
                    assert response.status_code == 404
                    assert await retained_rows(db_path) == before
        finally:
            for process in [child, *resumed]:
                if process.returncode is None:
                    process.kill()
                await process.communicate()


@pytest.mark.asyncio
# Layer: integration
async def test_retained_export_commit_binds_payload_and_rejects_substitution(test_root, workspace, monkeypatch):
    async with local_gitea() as server:
        for key, value in server.export_environment(str(test_root / "export-cache")).items():
            monkeypatch.setenv(key, value)
        output = workspace / "agent_output"
        await asyncio.to_thread(output.mkdir, exist_ok=True)
        original_payload = " original payload\n"
        await asyncio.to_thread((output / "result.txt").write_bytes, original_payload.encode("utf-8"))
        exporter = await asyncio.to_thread(create_gitea_artifact_exporter, workspace)
        run = {"run_id": "frozen-export", "run_type": "epic", "run_name": "proof", "build_id": "build",
               "session_status": "done", "summary": {"status": "done"}, "export_day": "2026-09-12",
               "export_time": "2026-09-12T12:00:00+00:00"}
        intent = await exporter.prepare_export(**run)
        async with httpx.AsyncClient(auth=(server.username, server.password)) as client:
            assert (await client.get(server.url + "/api/v1/repos/export-proof/artifacts")).status_code == 404
        await asyncio.to_thread((output / "result.txt").write_text, "changed after preparation", encoding="utf-8")
        receipt = await exporter.export_run(export_intent=intent, **run)
        assert receipt["commit"] == intent.commit
        # Read the owned server's repository independently of Orket and Gitea's
        # contents API, which has intermittently returned 500 even without metadata.
        content = await docker("exec", "--user", "git", server.container_id, "git", "--git-dir",
                               "/data/git/repositories/export-proof/artifacts.git", "show",
                               intent.commit + ":" + intent.run_path + "/agent_output/result.txt", strip_output=False)
        assert content == original_payload
        with pytest.raises(ValueError, match="E_GITEA_EXPORT_TREE_CONFLICT"):
            await exporter.reconcile_export(intent.model_copy(update={"tree": "f" * 40}))
        with pytest.raises(ValueError, match="E_GITEA_EXPORT_MANIFEST_CONFLICT"):
            await exporter.reconcile_export(intent.model_copy(update={"run_id": "different-run"}))
        pending = await exporter.prepare_export(**{**run, "run_id": "unpublished-export"})
        assert await exporter.reconcile_export(pending) is None
        response = await get_visible(server, "/api/v1/repos/export-proof/artifacts/commits")
        assert [item["sha"] for item in response.json()] == [intent.commit]
