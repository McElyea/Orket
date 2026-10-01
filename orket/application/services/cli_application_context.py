"""Own CLI logging preparation and extension setup for one command task."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from orket.adapters.observability.logging_context import bind_logging, prepare_logging, select_logging_inputs
from orket.application.services.extension_catalog_commands import prepare_extension_manager
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.extensions import ExtensionManager


@asynccontextmanager
async def open_cli_application(inputs: RuntimeConstructionInputs) -> AsyncIterator[ExtensionManager]:
    """The CLI command task enters and exits this setup scope, including command cleanup."""
    prepared = await prepare_logging(select_logging_inputs(inputs.invocation_root, inputs.environment))
    with bind_logging(prepared):
        manager = await prepare_extension_manager(construction_inputs=inputs)
        yield manager
