"""One acquired-resource cleanup owner for catalog and inference HTTP clients."""
import asyncio
import logging

from orket.adapters.execution.owned_io import run_owned_io
from orket.application.services.application_runtime_lifetime import close_owned_resource

LOGGER = logging.getLogger(__name__)


class ProviderHttpResources:
    def __init__(self):
        self._acquired = []

    def retain(self, resource):
        if not any(resource is existing for existing in self._acquired):
            self._acquired.append(resource)

    async def close(self):
        await run_owned_io(self._close, label="provider-http-cleanup", preserve_failure=True)

    async def _close(self):
        errors = []
        # Client teardown can fail midway; attempt each retained transport too.
        # HTTPX transport close is idempotent.
        for resource in reversed(self._acquired):
            try:
                await close_owned_resource(resource)
            except (Exception, asyncio.CancelledError) as exc:
                # Resource supervisor: attempt all teardown and retain every failure.
                LOGGER.error("Provider HTTP cleanup failed (%s)", type(resource).__name__, exc_info=True)
                errors.append(exc)
        if errors:
            raise BaseExceptionGroup("Provider HTTP cleanup failed", errors)
