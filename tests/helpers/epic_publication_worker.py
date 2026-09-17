"""Native process-death probe for the explicit control-plane closeout transaction."""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.runtime_result_projection import require_runtime_success
from orket.core.domain import RunState
from orket.settings import load_env
from tests.integration.test_epic_completion_publication import accept_publication_card, publication_pipeline


async def barrier(pipeline):
    ledger = await pipeline.run_ledger.get_run("publication-session")
    print(json.dumps({"barrier": True, "run_id": ledger["artifact_json"]["control_plane_run_record"]["run_id"],
                      "cp_db": pipeline.orchestrator.control_plane_execution_repository.db_path}), flush=True)
    await asyncio.Event().wait()


def install_barrier(pipeline, stage):
    if stage == "before_commit":
        original = AsyncControlPlaneExecutionRepository.save_run_record

        async def paused_write(repo, *, record):
            result = await original(repo, record=record)
            if record.lifecycle_state == RunState.COMPLETED:
                await barrier(pipeline)
            return result

        AsyncControlPlaneExecutionRepository.save_run_record = paused_write
    else:
        original = SQLiteControlPlaneTransactions.__call__

        @asynccontextmanager
        async def paused_commit(factory):
            async with original(factory) as transaction:
                yield transaction
            await barrier(pipeline)

        SQLiteControlPlaneTransactions.__call__ = paused_commit


async def main(root, workspace, db, mode):
    pipeline = await publication_pipeline(root, workspace, db)
    try:
        if mode == "resume":
            ledger = await pipeline.run_ledger.get_run("publication-session")
            run_id = ledger["artifact_json"]["control_plane_run_record"]["run_id"]
            run, attempt = await pipeline.cards_epic_control_plane.finalize_execution(run_id=run_id, session_status="done")
            print(json.dumps({"run_id": run.run_id, "state": run.lifecycle_state.value,
                              "attempt_state": attempt.attempt_state.value}), flush=True)
        else:
            async def execute_fixture(**_kwargs):
                await accept_publication_card(pipeline, workspace)

            pipeline.orchestrator.execute_epic = execute_fixture
            install_barrier(pipeline, mode)
            require_runtime_success(await pipeline.run_epic("publication_epic", build_id="build", session_id="publication-session"))
    finally:
        await pipeline.close()


if __name__ == "__main__":
    load_env()
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]))
