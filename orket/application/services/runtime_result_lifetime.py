"""Keep runtime owners alive until cleanup can be reflected in their result."""
import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult

logger = logging.getLogger(__name__)


async def execute_collection_member(*, create, creation, target, session_id, build_id, execution):
    construct, execution = partial(create, **creation), dict(execution)
    child = None
    cancelled = False
    result = RuntimeExecutionResult(session_id=session_id, build_id=build_id, observation="unresolved")
    try:
        child = await create_runtime_owner(construct, label="collection-member-construction")
        result = await child.run_card(target, session_id=session_id, build_id=build_id, **execution)
        if not isinstance(result, RuntimeExecutionResult):
            raise TypeError("E_RUNTIME_COLLECTION_EPIC_RESULT_REQUIRED")
    except RuntimeExecutionCancelled as exc:
        cancelled = True
        result = exc.result
    except asyncio.CancelledError:
        cancelled = True
        result = result.model_copy(update={"observation": "cancelled", "reason": "Collection member cancelled"})
    except Exception as exc:
        # Collection supervisor boundary: retain the declared identity and any
        # completed members when construction or execution cannot be confirmed.
        logger.exception("Collection member %s failed in session %s", target, session_id)
        result = RuntimeExecutionResult(session_id=session_id, build_id=build_id, observation="unresolved",
                                        reason=f"{type(exc).__name__}: {exc}")
    finally:
        if child is not None:
            try:
                cancelled = await close_runtime_owner(child) or cancelled
            except Exception as exc:
                logger.exception("Collection member cleanup failed in session %s", session_id)
                result = result.model_copy(update={"observation": "unresolved", "reason": f"Cleanup failed: {exc}"})
    if cancelled:
        raise RuntimeExecutionCancelled(result.model_copy(update={"observation": "cancelled"}))
    return result


async def close_runtime_owner(owner) -> bool:
    """Join owned cleanup through repeated caller cancellation and report it."""
    task = asyncio.create_task(owner.close())
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    return cancelled


async def create_runtime_owner(construct, *, label):
    """Close a completed runtime if interruption prevents transferring it to its caller."""
    created = []

    def create():
        owner = construct()
        created.append(owner)
        return owner

    try:
        return await run_owned_thread(create, label=label)
    except asyncio.CancelledError:
        if created:
            await close_runtime_owner(created[0])
        raise


@asynccontextmanager
async def open_runtime_owner(construct, *, label):
    owner = await create_runtime_owner(construct, label=label)
    body_returned = False
    try:
        yield owner
        body_returned = True
    finally:
        interrupted = await close_runtime_owner(owner)
        if interrupted and body_returned:
            raise asyncio.CancelledError("Runtime cleanup completed after caller cancellation")


@asynccontextmanager
async def open_configured_runtime(factory, workspace, *, label, construction_inputs=None, **options):
    """Capture bootstrap/path values before construction and own the returned runtime."""
    workspace = Path(workspace)
    options = dict(options)
    config_root = options.get("config_root")
    config_root = Path(config_root) if config_root is not None else None
    inputs = construction_inputs if construction_inputs is not None else await RuntimeConstructionInputs.capture_async()
    if config_root is not None:
        options["config_root"] = inputs.invocation_root / config_root
    construct = partial(factory, inputs.invocation_root / workspace, construction_inputs=inputs, **options)
    async with open_runtime_owner(construct, label=label) as owner:
        yield owner
