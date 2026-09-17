"""Layer: contract. Synthetic supervisor results test deadline/uncertainty translation."""
from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY, BuiltInConnectorRegistry
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("cleanup_confirmed", [False, True])
# Layer: contract
async def test_deadline_does_not_convert_unconfirmed_cleanup_into_timeout_receipt(tmp_path, caplog, cleanup_confirmed):
    lifetime = OwnedCommandResult(None, b"", b"", "cancelled", cleanup_confirmed, False,
                                  "unconfirmed", 101, None, None, ("fixture cleanup observation",))

    class InterruptedExecutor:
        async def invoke(self, *_args, **_kwargs):
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError as exc:
                raise CommandProcessCancelled(lifetime) from exc

    metadata = replace(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get("run_command"), timeout_seconds=0.01)
    service = OutwardConnectorService(connector_registry=BuiltInConnectorRegistry([metadata]),
                                     workspace_root=tmp_path, executor=InterruptedExecutor())
    if cleanup_confirmed:
        event = await service.invoke("run_command", {"command": ["fixture"]})
        assert event["outcome"] == "timeout"
        assert event["result_summary"]["process_lifetime"] == lifetime.lifetime()
    else:
        with pytest.raises(CommandExecutionUncertain) as failure:
            await service.invoke("run_command", {"command": ["fixture"]})
        assert failure.value.lifetime is lifetime
        event, = [row.orket_record["data"] for row in caplog.records
                  if row.message == "outward_connector_interrupted"]
        assert event["observation"] == "unresolved" and "outcome" not in event
        assert event["process_lifetime"] == lifetime.lifetime()


@pytest.mark.parametrize("cleanup_confirmed", [False, True])
# Layer: contract
async def test_external_cancellation_during_deadline_cleanup_preserves_typed_observation(tmp_path, cleanup_confirmed):
    lifetime = OwnedCommandResult(None, b"", b"", "cancelled", cleanup_confirmed, False,
                                  "unconfirmed", 101, None, None, ("fixture cleanup observation",))
    cancellation = CommandProcessCancelled(lifetime)
    cleanup_started, cleanup_release = asyncio.Event(), asyncio.Event()

    class InterruptedExecutor:
        async def invoke(self, *_args, **_kwargs):
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError as exc:
                cleanup_started.set()
                while not cleanup_release.is_set():
                    try:
                        await cleanup_release.wait()
                    except asyncio.CancelledError:
                        continue  # Explicit fixture models the real owner's cleanup wait.
                raise cancellation from exc

    metadata = replace(DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get("run_command"), timeout_seconds=0.01)
    service = OutwardConnectorService(connector_registry=BuiltInConnectorRegistry([metadata]),
                                     workspace_root=tmp_path, executor=InterruptedExecutor())
    task = asyncio.create_task(service.invoke("run_command", {"command": ["fixture"]}))
    try:
        await asyncio.wait_for(cleanup_started.wait(), 2)
        task.cancel()
        cleanup_release.set()
        with pytest.raises(CommandProcessCancelled) as failure:
            await task
        assert failure.value is cancellation and failure.value.lifetime is lifetime
    finally:
        cleanup_release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
