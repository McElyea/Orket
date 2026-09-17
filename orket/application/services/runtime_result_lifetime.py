"""Keep runtime owners alive until cleanup can be reflected in their result."""
import asyncio
import logging

from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult

logger = logging.getLogger(__name__)


async def execute_collection_member(*, create, creation, target, session_id, build_id, execution):
    child = None
    cancelled = False
    result = RuntimeExecutionResult(session_id=session_id, build_id=build_id, observation="unresolved")
    try:
        child = create(**creation)
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
