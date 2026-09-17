"""Killable worker at the effect/journal gap in standard epic publication."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.adapters.vcs.gitea_export_git import GiteaExportGit
from orket.application.services.epic_admission_service import EpicAdmissionService
from orket.application.services.epic_workload_outcome_service import EpicWorkloadOutcomeService
from orket.application.services.runtime_result_projection import require_runtime_success
from orket.core.contracts.gitea_export import GiteaExportIntent
from orket.exceptions import ExecutionFailed
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.settings import load_env
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline


def configure_local_export_probe(exporter):
    """Local effect injection exercises application uncertainty, not Git/Gitea."""
    async def prepare_export(**kwargs):
        return GiteaExportIntent(binding=exporter.binding(), run_id=kwargs["run_id"],
                                 commit="0" * 40, tree="1" * 40, run_path="local-effect-probe")

    async def reconcile_export(_export_intent):
        return None

    exporter.prepare_export = prepare_export
    exporter.reconcile_export = reconcile_export


async def main(root: Path, workspace: Path, db: str, mode: str, stage: str) -> None:
    if stage == "export_uncertain":
        os.environ["ORKET_GITEA_ARTIFACT_EXPORT"] = "1"
    pipeline = (await asyncio.to_thread(ExecutionPipeline, workspace, department="core", db_path=db, config_root=root)
                if mode in {"resume", "recover", "export_recover"} else await publication_pipeline(root, workspace, db))
    try:
        if stage == "export_uncertain":
            configure_local_export_probe(pipeline.artifact_exporter)
        if stage == "gitea_owner":
            configure_export_owner_probe(workspace, mode)
        async def execute_fixture(**_kwargs):
            if mode in {"resume", "export_recover"}:
                raise AssertionError("Publication recovery redispatched the workload")
            if mode in {"recover", "stale"}:
                await asyncio.to_thread(append_dispatch, workspace)
            await accept_publication_card(pipeline, workspace)
            if stage == "workload_unknown":
                await pause_worker(mode, stage)
            if stage == "outcome_failed":
                raise ExecutionFailed("retained native workload failure")

        pipeline.orchestrator.execute_epic = execute_fixture
        if mode == "resume" and stage in {"gitea_export", "gitea_intent"}:
            async def forbid_export(**_kwargs):
                raise AssertionError("Recovery repeated a Gitea push")
            pipeline.artifact_exporter.export_run = forbid_export
        if mode in {"kill", "stale"} and stage not in {"workload_unknown", "gitea_owner"}:
            target, method = {
                "ledger": (pipeline.run_ledger, "finalize_run"), "session": (pipeline.sessions, "complete_session"),
                "snapshot": (pipeline.snapshots, "record"), "success": (pipeline.success, "record_success"),
                "closeout": (pipeline.cards_epic_control_plane, "finalize_execution"),
                "receipts": (pipeline, "_materialize_protocol_receipts"),
                "summary": (pipeline, "_materialize_run_summary"),
                "export": (pipeline.artifact_exporter, "export_run"),
                "export_uncertain": (pipeline.artifact_exporter, "export_run"),
                "gitea_export": (pipeline.artifact_exporter, "export_run"),
                "gitea_intent": (pipeline.artifact_exporter, "export_run"),
                "outcome": (EpicWorkloadOutcomeService, "retain"),
                "outcome_failed": (EpicWorkloadOutcomeService, "retain"),
                "admission": (EpicAdmissionService, "claim"),
            }[stage]
            original = getattr(target, method)

            async def pause_after_effect(*args, **kwargs):
                if stage == "gitea_intent":
                    await pause_worker(mode, stage)
                if stage == "export_uncertain":
                    # This is a local effect probe, not a claim of live Gitea acceptance.
                    await asyncio.to_thread((workspace / "export-effect.txt").write_text, "effect occurred", encoding="utf-8")
                    result = {"commit": "effect-without-retained-receipt"}
                else:
                    result = await original(*args, **kwargs)
                await pause_worker(mode, stage)
                return result

            setattr(target, method, pause_after_effect)
        await execute_recovery_entry(pipeline, mode)
        ledger = await pipeline.run_ledger.get_run("publication-session")
        print(json.dumps({"status": ledger["status"], "run_id": ledger["artifact_json"]["control_plane_run_record"]["run_id"]}),
              flush=True)
    finally:
        await pipeline.close()


async def execute_recovery_entry(pipeline, mode):
    recovery = json.loads(os.environ["ORKET_TEST_EPIC_RECOVERY"]) if mode == "recover" else None
    export_recovery = json.loads(os.environ["ORKET_TEST_EPIC_EXPORT_RECOVERY"]) if mode == "export_recover" else None
    require_runtime_success(await pipeline.run_card("publication_epic", build_id="build", session_id="publication-session",
                                                   admission_recovery=recovery, export_recovery=export_recovery))


def configure_export_owner_probe(workspace, mode):
    """Hold only after committed ownership; count actual Git push-command admission."""
    transaction = SQLiteEpicPublicationRepository.transaction
    command = GiteaExportGit.command
    held = False

    @asynccontextmanager
    async def held_transaction(repository, session_id):
        nonlocal held
        pause = False
        async with transaction(repository, session_id) as current:
            yield current
            preparation = await current.get_preparation()
            if not held and mode in {"kill", "stale"} and preparation is not None and preparation.phase == 4:
                held, pause = True, True
        if pause:
            await pause_worker(mode, "gitea_owner")

    async def observed_command(git, *arguments, **kwargs):
        if arguments and arguments[0] == "push":
            await asyncio.to_thread(append_push, workspace)
        return await command(git, *arguments, **kwargs)

    SQLiteEpicPublicationRepository.transaction = held_transaction
    GiteaExportGit.command = observed_command


def append_push(workspace):
    with (workspace / "native-export-pushes.log").open("a", encoding="utf-8") as stream:
        stream.write("push\n")


def append_dispatch(workspace: Path) -> None:
    with (workspace / "native-recovery-dispatch.log").open("a", encoding="utf-8") as stream:
        stream.write("dispatch\n")


async def pause_worker(mode: str, stage: str) -> None:
    print(json.dumps({"barrier": True, "stage": stage}), flush=True)
    if mode == "stale":
        await asyncio.to_thread(sys.stdin.readline)
    else:
        await asyncio.Event().wait()


if __name__ == "__main__":
    load_env()
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]))
