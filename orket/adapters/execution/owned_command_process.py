"""Async transport to the package-owned OS supervisor, with no direct-child fallback."""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import secrets
import subprocess
import sys
from pathlib import Path

from orket.adapters.execution.owned_command_limits import jsonl_request_frames
from orket.adapters.execution.owned_command_limits import output_limit_bytes as validate_output_limit
from orket.core.contracts.owned_command import OwnedCommandResult

side_effecting = True
WORKER = Path(__file__).with_name("owned_command_worker.py")
_REASONS = {"completed", "timeout", "cancelled", "launch_failed", "cleanup_unconfirmed", "output_limit", "capture_incomplete", "protocol_failed"}


def _unconfirmed(process, diagnostic):
    return OwnedCommandResult(None, b"", b"", "cleanup_unconfirmed", False, False,
                              "unconfirmed", process.pid, None, None, (diagnostic,))


def _decode(process, raw, request_id):
    try:
        record = json.loads(raw)
        if (process.returncode != 0 or record["schema_version"] != "owned_command.v1" or record["request_id"] != request_id
                or type(record["supervisor_pid"]) is not int or record["supervisor_pid"] <= 0
                or record["reason"] not in _REASONS or type(record["cleanup_confirmed"]) is not bool
                or type(record["capture_complete"]) is not bool
                or record["backend"] not in {"windows_job", "linux_subreaper", "unavailable"}
                or (record.get("command_pid") is not None and type(record["command_pid"]) is not int)
                or not isinstance(record["diagnostics"], list)
                or any(not isinstance(item, str) for item in record["diagnostics"])
                or (record["returncode"] is not None and type(record["returncode"]) is not int)
                or (record["reason"] == "completed" and
                    (not record["cleanup_confirmed"] or not record["capture_complete"] or record["returncode"] is None
                     or type(record.get("command_pid")) is not int or record["command_pid"] <= 0
                     or record["backend"] != ("windows_job" if os.name == "nt" else "linux_subreaper")))):
            raise ValueError("Invalid supervisor lifetime")
        return OwnedCommandResult(record["returncode"], base64.b64decode(record["stdout"], validate=True),
                                  base64.b64decode(record["stderr"], validate=True), record["reason"],
                                  record["cleanup_confirmed"], record["capture_complete"], record["backend"],
                                  process.pid, record["supervisor_pid"], record.get("command_pid"), tuple(record["diagnostics"]))
    except (ValueError, TypeError, KeyError):
        return _unconfirmed(process, f"supervisor_protocol_invalid:exit={process.returncode}")


async def _drain(stream, buffer):
    while chunk := await stream.read(16384):
        buffer.extend(chunk)


async def _collect(process, buffers):
    await asyncio.gather(_drain(process.stdout, buffers[0]), _drain(process.stderr, buffers[1]), process.wait())
    return bytes(buffers[0]), bytes(buffers[1])


async def _stop_and_collect(process, collected, buffers, request_id):
    if collected.cancelling():
        # Event-loop shutdown cancels collectors too. Retain already-read bytes,
        # settle the cancelled readers, then resume capture under the cleanup owner.
        await asyncio.gather(collected, return_exceptions=True)
        collected = asyncio.create_task(_collect(process, buffers))
    try:
        process.stdin.write(b"stop\n")
        await process.stdin.drain()
    except OSError:
        pass  # The retained result or missing protocol below determines certainty.
    try:
        raw, _ = await asyncio.wait_for(asyncio.shield(collected), timeout=6)
        return _decode(process, raw, request_id)
    except (TimeoutError, OSError) as failure:
        # A dead/unresponsive Linux subreaper is not proof that descendants exited.
        # Windows kill-on-close may terminate them; absence of an ack stays uncertain.
        diagnostic = ("supervisor_cleanup_deadline_exceeded" if isinstance(failure, TimeoutError)
                      else f"supervisor_capture:{type(failure).__name__}:{failure.errno}")
        try:
            if process.returncode is None:
                process.kill()
        except OSError as exc:
            diagnostic += f":terminate:{type(exc).__name__}:{exc.errno}"
        try:
            await asyncio.wait_for(asyncio.shield(collected), timeout=1)
        except (TimeoutError, OSError):
            collected.cancel()
            await asyncio.gather(collected, return_exceptions=True)
            diagnostic += f":supervisor_exit_confirmed={process.returncode is not None}"
        return _unconfirmed(process, diagnostic)


async def _finish_stop(process, collected, buffers, request_id):
    cleanup = asyncio.create_task(_stop_and_collect(process, collected, buffers, request_id))
    while True:
        try:
            return await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            if cleanup.cancelled():
                cleanup = asyncio.create_task(_stop_and_collect(process, collected, buffers, request_id))


async def execute_owned_command(*, argv, cwd, environment, timeout_seconds, input_data, stop, output_limit_bytes=None,
                                jsonl_requests=None, io_timeout_seconds=None):
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("E_VERIFICATION_COMMAND_TIMEOUT_INVALID")
    # Windows venv launchers have a different PID from the actual interpreter.
    # Bind this private transport with a nonce, retaining both PIDs as observations.
    request_id = secrets.token_hex(16)
    request = {"request_id": request_id, "argv": list(argv), "cwd": str(cwd), "env": environment, "timeout": timeout_seconds,
               "output_limit_bytes": validate_output_limit(output_limit_bytes),
               "stop_requested": False,
               "input": base64.b64encode(input_data).decode("ascii") if input_data is not None else None}
    if jsonl_requests is not None:
        if (input_data is not None or io_timeout_seconds is None
                or not math.isfinite(io_timeout_seconds) or io_timeout_seconds <= 0):
            raise ValueError("E_COMMAND_JSONL_OPTIONS_INVALID")
        request.update(jsonl_frames=[base64.b64encode(frame).decode("ascii") for frame in jsonl_request_frames(jsonl_requests)],
                       jsonl_timeout=io_timeout_seconds)
    payload = json.dumps(request).encode() + b"\n"
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError("E_VERIFICATION_COMMAND_INPUT_LIMIT")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-S", str(WORKER), stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **options)
    buffers = (bytearray(), bytearray())
    collected = asyncio.create_task(_collect(process, buffers))
    stopping = asyncio.create_task(stop.wait())
    try:
        if stop.is_set():
            request["stop_requested"] = True
            payload = json.dumps(request).encode() + b"\n"
        process.stdin.write(payload)
        await process.stdin.drain()
        done, _ = await asyncio.wait({collected, stopping}, timeout=timeout_seconds + 8, return_when=asyncio.FIRST_COMPLETED)
        if collected in done:
            raw, _ = await collected
            return _decode(process, raw, request_id)
        return await _finish_stop(process, collected, buffers, request_id)
    except (OSError, asyncio.CancelledError):
        stop.set()
        return await _finish_stop(process, collected, buffers, request_id)
    finally:
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)
        process.stdin.close()
