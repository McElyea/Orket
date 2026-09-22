"""Capture catalog inputs and retain native construction and asynchronous teardown."""
from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.llm.provider_catalog_client import build_provider_catalog_client
from orket.application.services.process_input_service import absolute_process_path, capture_process_context
from orket.application.services.provider_http_resources import ProviderHttpResources
from orket.core.contracts.provider_http import ProviderHttpInputs
from orket.decision_nodes.provider_http_policy import provider_proxy_mounts


def capture_provider_http_inputs(*, environment: Mapping[str, str] | None = None, cwd: Path | None = None):
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    paths = [absolute_process_path(captured[key], directory) if captured.get(key) else None
             for key in ("SSL_CERT_FILE", "SSL_CERT_DIR", "SSLKEYLOGFILE")]
    return ProviderHttpInputs(provider_proxy_mounts(captured), *paths)


@asynccontextmanager
async def open_provider_catalog_client(*, base_url: str, timeout_s: float, api_key: str | None = None,
                                      environment: Mapping[str, str] | None = None, cwd: Path | None = None):
    inputs = capture_provider_http_inputs(cwd=cwd, environment=environment)
    budget = float(timeout_s)
    if not math.isfinite(budget):
        raise ValueError("E_PROVIDER_HTTP_TIMEOUT_NOT_FINITE")
    resources = ProviderHttpResources()

    def construct():
        client = build_provider_catalog_client(inputs=inputs, base_url=base_url,
            timeout_s=max(1.0, budget), api_key=api_key, own_resource=resources.retain)
        return client

    failure = None
    try:
        client = await run_owned_thread(construct, label="provider-http-construction")
        yield client
    except BaseException as exc:
        # Retain the catalog outcome while cleanup is independently owned.
        failure = exc
    try:
        await resources.close()
    except asyncio.CancelledError:
        if failure is None:
            raise
    except BaseException as cleanup_failure:
        if failure is not None and failure is not cleanup_failure:
            raise BaseExceptionGroup("Provider HTTP operation and cleanup failed", [failure, cleanup_failure]) from None
        raise
    if failure is not None:
        raise failure
