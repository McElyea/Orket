from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket_extension_sdk.result import WorkloadResult

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


async def run_sdk_workload_in_subprocess(
    *,
    extension: ExtensionRecord,
    workload: _ExtensionManifestEntry,
    sdk_ctx: Any,
    input_payload: dict[str, Any],
    authorization_envelope: SdkAuthorizationEnvelope,
    audit_case: SdkCapabilityAuditCase,
    child_extra_capabilities: tuple[str, ...] = (),
) -> SdkSubprocessRunResult:
    """Run SDK workload code outside the host interpreter with manifest import limits."""
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
        "child_extra_capabilities": list(child_extra_capabilities),
    }
    try:
        request_bytes = json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except TypeError as exc:
        raise ValueError("E_SDK_SUBPROCESS_INPUT_NOT_JSON") from exc

    with tempfile.TemporaryDirectory(prefix="orket-sdk-workload-") as temp_dir:
        request_path = Path(temp_dir) / "request.json"
        result_path = Path(temp_dir) / "result.json"
        await asyncio.to_thread(request_path.write_bytes, request_bytes)

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "orket.extensions.sdk_workload_subprocess",
            str(request_path),
            str(result_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        try:
            result_bytes = await asyncio.to_thread(result_path.read_bytes)
        except FileNotFoundError as exc:
            raise RuntimeError("E_SDK_WORKLOAD_SUBPROCESS_RESULT_MISSING") from exc

    try:
        result_payload = json.loads(result_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("E_SDK_WORKLOAD_SUBPROCESS_RESULT_INVALID_JSON") from exc
    if process.returncode != 0:
        detail = str(result_payload.get("error_message") or _trim_process_output(stderr or stdout))
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
