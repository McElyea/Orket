"""Capture catalog inputs and retain native construction and asynchronous teardown."""
from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.llm.provider_catalog_client import build_provider_catalog_client
from orket.application.services.process_input_service import absolute_process_path, capture_process_context
from orket.core.contracts.provider_http import ProviderHttpInputs
from orket.decision_nodes.provider_http_policy import provider_proxy_mounts

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def open_provider_catalog_client(*, base_url: str, timeout_s: float, api_key: str | None = None,
                                      environment: Mapping[str, str] | None = None, cwd: Path | None = None):
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    budget = float(timeout_s)
    if not math.isfinite(budget):
        raise ValueError("E_PROVIDER_HTTP_TIMEOUT_NOT_FINITE")
    paths = [absolute_process_path(captured[key], directory) if captured.get(key) else None
             for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE")]
    inputs = ProviderHttpInputs(provider_proxy_mounts(captured), *paths)
    acquired = []

    def construct():
        client = build_provider_catalog_client(inputs=inputs, base_url=base_url,
            timeout_s=max(1.0, budget), api_key=api_key, own_resource=acquired.append)
        return client

    async def cleanup():
        # Also attempt individual transports if client teardown fails midway.
        # HTTPX transport close is idempotent; every acquired resource is retained.
        errors = []
        for resource in reversed(acquired):
            try:
                await resource.aclose()
            except (Exception, asyncio.CancelledError) as exc:
                # This resource supervisor attempts all teardown and reports every failure.
                LOGGER.error("Provider HTTP cleanup failed (%s)", type(resource).__name__, exc_info=True)
                errors.append(exc)
        if errors:
            raise BaseExceptionGroup("Provider HTTP cleanup failed", errors)

    failure = None
    try:
        client = await run_owned_thread(construct, label="provider-http-construction")
        yield client
    except BaseException as exc:
        # Retain the catalog outcome while cleanup is independently owned.
        failure = exc
    try:
        await run_owned_io(cleanup, label="provider-http-cleanup", preserve_failure=True)
    except asyncio.CancelledError:
        if failure is None:
            raise
    except BaseException as cleanup_failure:
        if failure is not None and failure is not cleanup_failure:
            raise BaseExceptionGroup("Provider HTTP operation and cleanup failed", [failure, cleanup_failure]) from None
        raise
    if failure is not None:
        raise failure
