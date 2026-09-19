from __future__ import annotations

import asyncio
import json
import math
import sys
from dataclasses import dataclass
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.sdk_workload_exchange import SdkWorkloadExchange
from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.logging import log_event
from orket_extension_sdk.result import WorkloadResult

from .controller_dispatcher_contract import DEFAULT_CHILD_TIMEOUT_SECONDS
from .models import ExtensionRecord, _ExtensionManifestEntry
from .sdk_capability_authorization import SdkAuthorizationEnvelope, SdkCapabilityAuditCase


@dataclass(frozen=True)
class SdkSubprocessRunResult:
    workload_result: WorkloadResult
    capability_report: dict[str, Any]


class SdkSubprocessRunError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "", capability_report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.capability_report = dict(capability_report or {})


class SdkSubprocessExecutionUncertain(RuntimeError):
    """Retain unresolved dispatch; a missing observation is not a no-effect receipt."""

    def __init__(self, phase: str, lifetime: OwnedCommandResult | None, exchange: SdkWorkloadExchange):
        super().__init__(f"E_SDK_SUBPROCESS_EXECUTION_UNCERTAIN: {phase}")
        self.phase = phase
        self.lifetime = lifetime
        self.exchange_path = exchange.root


async def run_sdk_workload_in_subprocess(
    *,
    extension: ExtensionRecord,
    workload: _ExtensionManifestEntry,
    sdk_ctx: Any,
    input_payload: dict[str, Any],
    authorization_envelope: SdkAuthorizationEnvelope,
    audit_case: SdkCapabilityAuditCase,
    child_extra_capabilities: tuple[str, ...] = (),
    timeout_seconds: float = DEFAULT_CHILD_TIMEOUT_SECONDS,
) -> SdkSubprocessRunResult:
    """Own trusted SDK execution through native cleanup and result adoption."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("E_SDK_SUBPROCESS_TIMEOUT_INVALID")
    request_bytes = _request_bytes(extension, workload, sdk_ctx, input_payload,
                                   authorization_envelope, audit_case, child_extra_capabilities)
    return await _SdkProcessOwner(sdk_ctx.workspace_root).run(request_bytes, timeout_seconds)


class _SdkProcessOwner:
    def __init__(self, workspace):
        self.workspace = workspace
        self.exchange = SdkWorkloadExchange()
        self.lifetime: OwnedCommandResult | None = None
        self.dispatched = self.retain = False
        self.phase = "prepare"

    async def run(self, request_bytes, timeout_seconds):
        try:
            await run_owned_thread(lambda: self.exchange.prepare(request_bytes), label="sdk-exchange-prepare")
            return await self._execute(timeout_seconds)
        except CommandProcessCancelled as exc:
            self.lifetime = exc.lifetime
            if not self.lifetime.cleanup_confirmed:
                raise await self._uncertain("cancel-cleanup") from exc
            # asyncio.timeout in 3.12 converts the exact base cancellation type.
            # Keep the native observation as the cause and in its retained event.
            raise asyncio.CancelledError from exc
        except SdkSubprocessRunError:
            raise
        except SdkSubprocessExecutionUncertain:
            self.retain = True
            raise
        except asyncio.CancelledError as exc:
            if self.dispatched and (self.lifetime is None or not self.lifetime.cleanup_confirmed):
                raise await self._uncertain("cancel-observation") from exc
            raise
        except Exception as exc:
            # This process supervision boundary preserves unknown effects and the
            # original cause instead of permitting an invented terminal receipt.
            if not self.dispatched:
                raise
            raise await self._uncertain(self.phase) from exc
        finally:
            if not self.retain:
                try:
                    await run_owned_thread(self.exchange.remove, label="sdk-exchange-remove")
                except (OSError, RuntimeError) as exc:
                    raise await self._uncertain("exchange-remove") from exc

    async def _uncertain(self, phase):
        self.retain = True
        error = SdkSubprocessExecutionUncertain(phase, self.lifetime, self.exchange)
        observation = {"phase": phase, "exchange_path": str(self.exchange.root) if self.exchange.root else None,
                       "process_lifetime": self.lifetime.lifetime() if self.lifetime else None}
        try:
            await run_owned_thread(lambda: log_event("sdk_workload_process_uncertain", observation, self.workspace),
                                   label="sdk-uncertainty-observation")
        except (Exception, asyncio.CancelledError) as exc:
            # Diagnostic publication is a final supervision boundary. Its failure
            # must not turn unknown execution into ordinary failure/cancellation.
            error.add_note(f"Uncertainty diagnostic failed: {type(exc).__name__}")
            error.diagnostic_error = exc
        return error

    async def _execute(self, timeout_seconds):
        self.phase, self.dispatched = "native-execution", True
        exchange = self.exchange
        supervisor = CommandProcessSupervisor(self.workspace, cancellation_event="sdk_workload_process_cancelled")
        self.lifetime = await supervisor.run(
            [sys.executable, "-m", "orket.extensions.sdk_workload_subprocess",
             str(exchange.root / "request.json"), str(exchange.root / "result.json")],
            cwd=exchange.cwd, timeout_seconds=timeout_seconds,
        )
        self.phase = "lifetime-observation"
        lifetime = self.lifetime
        await run_owned_thread(lambda: log_event("sdk_workload_process_observed", lifetime.lifetime(),
                                                self.workspace), label="sdk-lifetime-observation")
        if lifetime.reason != "completed" or not lifetime.cleanup_confirmed or not lifetime.capture_complete:
            raise await self._uncertain("native-" + lifetime.reason)
        self.phase = "result-read"
        raw = await run_owned_thread(exchange.read_result, label="sdk-exchange-read")
        self.phase = "result-adoption"
        return _adopt_result(raw, lifetime)


def _request_bytes(extension, workload, sdk_ctx, input_payload, authorization_envelope, audit_case, extra_capabilities):
    request_payload = {
        "extension": {
            "extension_id": extension.extension_id,
            "extension_version": extension.extension_version,
            "path": extension.path,
            "allowed_stdlib_modules": list(extension.allowed_stdlib_modules),
        },
        "workload": {
            "workload_id": workload.workload_id,
            "workload_version": workload.workload_version,
            "entrypoint": workload.entrypoint,
        },
        "context": {
            "run_id": sdk_ctx.run_id,
            "workspace_root": str(sdk_ctx.workspace_root),
            "input_dir": str(sdk_ctx.input_dir),
            "output_dir": str(sdk_ctx.output_dir),
            "seed": sdk_ctx.seed,
            "config": dict(sdk_ctx.config),
        },
        "input_payload": dict(input_payload),
        "authorization_envelope": authorization_envelope.to_payload(),
        "audit_case": audit_case.as_dict(),
        "child_extra_capabilities": list(extra_capabilities),
    }
    try:
        return json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except TypeError as exc:
        raise ValueError("E_SDK_SUBPROCESS_INPUT_NOT_JSON") from exc


def _adopt_result(raw: bytes, lifetime: OwnedCommandResult) -> SdkSubprocessRunResult:
    result_payload = json.loads(raw.decode("utf-8"))
    if (not isinstance(result_payload, dict) or type(result_payload.get("ok")) is not bool
            or result_payload["ok"] is not (lifetime.returncode == 0)
            or not isinstance(result_payload.get("capability_report"), dict)):
        raise ValueError("E_SDK_WORKLOAD_SUBPROCESS_RESULT_INVALID")
    if lifetime.returncode != 0:
        if not isinstance(result_payload.get("error_message"), str) or not isinstance(result_payload.get("error_code"), str):
            raise ValueError("E_SDK_WORKLOAD_SUBPROCESS_ERROR_INVALID")
        detail = str(result_payload["error_message"] or _trim_process_output(lifetime.stderr or lifetime.stdout))
        error_code = str(result_payload.get("error_code") or "")
        raise SdkSubprocessRunError(
            f"E_SDK_WORKLOAD_SUBPROCESS_FAILED: {detail}",
            error_code=error_code,
            capability_report=dict(result_payload.get("capability_report", {})),
        )
    return SdkSubprocessRunResult(
        workload_result=WorkloadResult.model_validate(result_payload["workload_result"]),
        capability_report=dict(result_payload.get("capability_report", {})),
    )


def _trim_process_output(payload: bytes, *, limit: int = 4000) -> str:
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        return "no stderr"
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"
