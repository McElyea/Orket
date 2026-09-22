"""One native construction boundary retains both acquisition and cleanup failures."""
import logging

from orket.adapters.execution.owned_io import require_sync_context
from orket.capabilities.sync_bridge import run_coro_sync

LOGGER = logging.getLogger(__name__)


def construct_with_owned_cleanup(construct, *, owner, label):
    require_sync_context(code="E_NATIVE_CONSTRUCTION_REQUIRES_ASYNC_OWNER")
    try:
        return construct()
    except BaseException as failure:
        # Native construction supervisor owns resources before a result exists.
        LOGGER.error("%s failed (%s)", label, type(failure).__name__)
        try:
            run_coro_sync(owner.close())
        except BaseException as cleanup_failure:
            raise BaseExceptionGroup(label + " and cleanup failed", [failure, cleanup_failure]) from None
        raise
