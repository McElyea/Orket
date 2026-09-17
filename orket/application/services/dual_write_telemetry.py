"""Application-owned observation of mirrored ledger outcomes."""
import inspect
import logging

from orket.adapters.execution.owned_io import run_owned_thread
from orket.logging import log_event
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class DualWriteTelemetry:
    def __init__(self, sink):
        self.sink, self.failure_count = sink, 0

    async def emit(self, payload):
        try:
            if self.sink is None:
                await run_owned_thread(lambda: log_event(payload["kind"], payload, role="system"),
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
                await run_owned_thread(lambda: log_event("telemetry_sink_error", diagnostic, role="system"),
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
