"""Application-owned observation of mirrored ledger outcomes."""
import inspect
import logging
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR, capture_log_event_inputs
from orket.logging import log_event
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class DualWriteTelemetry:
    def __init__(self, sink, *, workspace: Path):
        self.sink, self.failure_count = sink, 0
        self.workspace = workspace

    async def emit(self, payload):
        workspace = self.workspace
        try:
            if self.sink is None:
                if type(payload) is not dict:
                    raise TypeError(LOG_EVENT_INPUT_ERROR)
                event, captured = capture_log_event_inputs(payload["kind"], payload)
                await run_owned_thread(partial(log_event, event, captured, workspace=workspace, role="system"),
                                       label="dual-ledger-telemetry")
            else:
                # Sync sinks may perform I/O. A returned awaitable still runs on the owning loop.
                outcome = await run_owned_thread(lambda: self.sink(payload), label="dual-ledger-telemetry-sink")
                if inspect.isawaitable(outcome):
                    await outcome
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            self.failure_count += 1
            diagnostic = {"component": "run_ledger_dual_write", "error_type": type(exc).__name__, "error": str(exc)}
            try:
                event, captured = capture_log_event_inputs("telemetry_sink_error", diagnostic)
                await run_owned_thread(partial(log_event, event, captured, workspace=workspace, role="system"),
                                       label="dual-ledger-telemetry-error")
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as diagnostic_error:
                failure = (type(diagnostic_error), diagnostic_error, diagnostic_error.__traceback__)
                await run_owned_thread(lambda: logging.getLogger(__name__).error(
                    "Dual ledger telemetry error could not be retained", exc_info=failure),
                    label="dual-ledger-telemetry-fallback")

    async def parity(self, *, sqlite_repo, protocol_repo, phase, session_id, protocol_error):
        payload = {"kind": "run_ledger_dual_write_parity", "phase": phase, "session_id": session_id,
                   "parity_ok": False, "difference_count": 0, "differences": [], "sqlite_digest": None,
                   "protocol_digest": None, "protocol_error": protocol_error,
                   "parity_error": None, "parity_check_error": False}
        if protocol_error is not None:
            payload["parity_skip_reason"] = "protocol_write_failed"
        else:
            try:
                parity = await compare_run_ledger_rows(sqlite_repo=sqlite_repo, protocol_repo=protocol_repo,
                                                       session_id=session_id)
                payload.update({key: parity[key] for key in ("parity_ok", "differences", "sqlite_digest", "protocol_digest")})
                payload["difference_count"] = len(payload["differences"])
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
                payload.update(parity_error=f"{type(exc).__name__}:{exc}", parity_check_error=True)
        await self.emit(payload)
