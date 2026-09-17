"""Native fixture process stopped after the real guarded approval claim commits."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from orket.runtime.execution import epic_run_result_boundary as boundary
from orket.runtime.execution.epic_run_orchestrator import EpicRunOrchestrator
from tests.integration.test_epic_approval_continuation import approval_engine, pause


async def main(root: Path, decision: str, stage: str):
    with pytest.MonkeyPatch.context() as patch:
        async with approval_engine(root, patch, setup=True) as engine:
            approval = await pause(engine)
            restore = boundary.restore_approval_context
            execute = EpicRunOrchestrator._execute_workload

            async def announce(retained):
                print(json.dumps({"barrier": "approval_claim_committed", "pause_digest": retained.digest(),
                                  "runtime_db": str(engine._pipeline.db_path),
                                  "approval_id": approval["approval_id"],
                                  "child_run": approval["control_plane_target_ref"]}), flush=True)
                assert (await asyncio.to_thread(sys.stdin.readline)).strip() == "resume"

            async def held_restore(owner, setup, retained):
                context = await restore(owner, setup, retained)
                if stage == "claimed":
                    await announce(retained)
                return context

            async def held_execute(owner, context):
                await execute(owner, context)
                if stage == "post_effect":
                    async with owner.publication.repository.transaction("approval-session") as tx:
                        retained = await tx.approval_pauses.latest()
                    await announce(retained)

            patch.setattr(boundary, "restore_approval_context", held_restore)
            patch.setattr(EpicRunOrchestrator, "_execute_workload", held_execute)
            result = await engine.decide_approval(approval_id=approval["approval_id"], decision=decision)
            assert result["runtime_result"]["observation"] == "published"
            assert result["runtime_result"]["succeeded"] is (decision == "approve")


async def recover(root: Path, request):
    with pytest.MonkeyPatch.context() as patch:
        async with approval_engine(root, patch) as engine:
            print(json.dumps({"barrier": "recovery_caller_ready"}), flush=True)
            assert (await asyncio.to_thread(sys.stdin.readline)).strip() == "recover"
            result = await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build",
                                           approval_recovery=request)
            print(json.dumps({"result": result.observation, "succeeded": result.succeeded, "reason": result.reason}), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "recover":
        asyncio.run(recover(Path(sys.argv[2]), json.loads(sys.argv[3])))
    else:
        asyncio.run(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
