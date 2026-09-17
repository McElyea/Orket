"""Actual CLI entry with explicit model/policy fixtures and real retained stores.

This process never supplies a runtime result or replaces publication/finalization.
The incomplete case injects loss of build membership before dispatch; approval
uses the supported custom loop-policy seam. These are not stock CLI policy flags.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import pytest

import orket
import orket.interfaces.cli as cli_module
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.cli import main as cli_main
from orket.orchestration.engine import OrchestrationEngine
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.integration.test_system_acceptance_flow import (
    ToolApprovalContinuationProvider,
    _build_assets,
    _patch_provider,
)


async def interrupt_when_requested(root, caller, case):
    for _ in range(600):
        if await asyncio.to_thread((root / "interrupt-now").exists):
            if case == "signal":
                signal.raise_signal(signal.SIGINT)
            else:
                caller.cancel()
                await asyncio.sleep(0)
                caller.cancel()
            return
        await asyncio.sleep(0.025)
    raise RuntimeError("Acceptance driver did not request interruption")


async def native_workload(root, case):
    children = root / "children"
    await asyncio.to_thread(children.mkdir)
    worker = Path(__file__).parents[1] / "integration/verification_lifetime_worker.py"
    interrupter = asyncio.create_task(interrupt_when_requested(root, asyncio.current_task(), case))
    try:
        await asyncio.to_thread((root / "fixture-bootstrap-ready").touch)
        await CommandProcessSupervisor(root / "workspace", cancellation_event="verification_process_cancelled").run(
            [sys.executable, str(worker), str(children), "2", "detached", "ignore-term"],
            cwd=children, environment=dict(os.environ), timeout_seconds=15,
        )
    finally:
        if not interrupter.done():
            interrupter.cancel()
        await asyncio.gather(interrupter, return_exceptions=True)


def configure_engine(root, case):
    def create(workspace, department):
        engine = OrchestrationEngine(workspace, department, db_path=str(root / "cards.db"), config_root=root)
        pipeline = engine._pipeline
        if case == "pending":
            pipeline.orchestrator.loop_policy_node.approval_required_tools_for_seat = (
                lambda seat_name, **_: ["write_file"] if seat_name == "lead_architect" else [])
        else:
            original = pipeline.orchestrator.execute_epic

            async def workload(**kwargs):
                if case == "incomplete":
                    # Fault injection changes real storage; the actual runtime
                    # determines incomplete truth and publishes its own result.
                    card = await pipeline.async_cards.get_by_id("ISSUE-A")
                    card.build_id = "outside-observed-build"
                    await pipeline.async_cards.save(card)
                    await original(**kwargs)
                else:
                    await native_workload(root, case)

            pipeline.orchestrator.execute_epic = workload
        return engine

    return create


def main():
    root, case, alias = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    assert case in {"pending", "incomplete", "signal", "repeated-cancel"}
    assert alias in {"card", "epic", "rock"}
    (root / "workspace").mkdir()
    _build_assets(root, with_guard=False, epic_id="lifecycle", expected_file="approved.txt", expected_text="approved")
    with pytest.MonkeyPatch.context() as patch:
        _patch_provider(patch, ToolApprovalContinuationProvider())
        patch.setattr(cli_module, "OrchestrationEngine", configure_engine(root, case))
        code = cli_main(["runtime", "--" + alias, "lifecycle", "--workspace", str(root / "workspace"),
                         "--build-id", "lifecycle-build"])
    write_payload_with_diff_ledger(root / "cli-observation.json", {
        "proof": "native CLI with explicit model/policy/storage fixtures", "path": "primary",
        "result": "success" if code == (130 if case in {"signal", "repeated-cancel"} else 1) else "failure",
        "case": case, "alias": alias, "returncode": code, "runtime_origin": orket.__file__,
    })
    raise SystemExit(code)


if __name__ == "__main__":
    main()
