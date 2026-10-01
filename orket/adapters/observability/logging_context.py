"""Application values borrow the single publication owner; binding performs no I/O."""
from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.adapters.observability import log_publication
from orket.core.contracts.logging_inputs import LOG_QUEUE_MAX_ENV, MISSING_WORKSPACE_MODE_ENV, LoggingInputs

side_effecting = True
LOGGING_PREPARATION_REQUIRED = "E_LOGGING_PREPARATION_REQUIRED"


@dataclass(frozen=True)
class PreparedLogging:
    inputs: LoggingInputs

    def __post_init__(self) -> None:
        if type(self.inputs) is not LoggingInputs:
            raise TypeError("E_LOGGING_PREPARATION_INPUT_UNSUPPORTED")


_application: ContextVar[PreparedLogging | None] = ContextVar("orket_prepared_logging", default=None)


def select_logging_inputs(invocation_root: Path, environment) -> LoggingInputs:
    """Select scalars from an application's already-captured standard environment mapping."""
    return LoggingInputs.select(invocation_root, timezone=environment.get("ORKET_TIMEZONE", ""),
        missing_workspace=environment.get(MISSING_WORKSPACE_MODE_ENV, ""),
        queue_max=environment.get(LOG_QUEUE_MAX_ENV, ""))


def native_logging_inputs() -> LoggingInputs:
    require_sync_context(code="E_LOGGING_NATIVE_CAPTURE_REQUIRES_NATIVE_CONTEXT")
    return select_logging_inputs(Path.cwd(), dict(os.environ))


def prepare_logging_native(inputs: LoggingInputs) -> PreparedLogging:
    require_sync_context(code="E_LOGGING_PREPARATION_REQUIRES_NATIVE_CONTEXT")
    if type(inputs) is not LoggingInputs:
        raise TypeError("E_LOGGING_PREPARATION_INPUT_UNSUPPORTED")
    log_publication.prepare_log_writer(inputs.queue_max)
    return PreparedLogging(inputs)


async def prepare_logging(inputs: LoggingInputs) -> PreparedLogging:
    return await run_owned_thread(lambda: prepare_logging_native(inputs), label="logging-preparation")


@contextmanager
def bind_logging(prepared: PreparedLogging):
    if type(prepared) is not PreparedLogging:
        raise TypeError("E_LOGGING_PREPARATION_INPUT_UNSUPPORTED")
    token = _application.set(prepared)
    try:
        yield prepared
    finally:
        _application.reset(token)


@overload
def selected_logging(*, required: Literal[True] = True) -> PreparedLogging: ...


@overload
def selected_logging(*, required: Literal[False]) -> PreparedLogging | None: ...


@overload
def selected_logging(*, required: bool) -> PreparedLogging | None: ...


def selected_logging(*, required: bool = True) -> PreparedLogging | None:
    prepared = _application.get()
    if prepared is None and required:
        raise RuntimeError(LOGGING_PREPARATION_REQUIRED)
    if prepared is not None:
        log_publication.require_prepared_logging(prepared.inputs.queue_max)
    return prepared
