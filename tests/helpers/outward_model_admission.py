from __future__ import annotations

import asyncio

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from tests.helpers.outward_authorization import outward_api
from tests.helpers.outward_effect_worker import CountedModelClient


async def admission_snapshot(db_path, *, turn=1):
    unit = OutwardStoreUnitOfWork(
        approvals=OutwardApprovalStore(db_path), runs=OutwardRunStore(db_path), events=OutwardRunEventStore(db_path),
    )
    async with unit.transaction() as transaction:
        return await transaction.models.get("bt0-run", 1, turn, turn - 1)


async def queue_run(root, inputs, calls):
    """Use the submission service to leave a normal queued run before public worker startup."""
    async with outward_api(root, inputs) as (_client, context):
        return await context.outward_run_service.submit({
            "run_id": "bt0-run",
            "task": {"description": "Model admission crash proof", "instruction": "Write each approved file.",
                     "acceptance_contract": {"governed_tool_sequence": calls}},
            "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": len(calls)},
        })


async def retry_run(client, run):
    return await client.post("/v1/runs", json={"run_id": run.run_id, "task": run.task})


async def count_calls(root):
    try:
        data = await asyncio.to_thread((root / "model_invocations.txt").read_text)
    except FileNotFoundError:
        return 0
    return len(data.splitlines())


def use_counted_model(monkeypatch, root, calls):
    import orket.application.services.outward_model_tool_call_service as model_module

    monkeypatch.setattr(model_module, "create_configured_model_client", lambda: CountedModelClient(root, calls))
