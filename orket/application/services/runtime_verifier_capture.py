"""Loss-aware diagnostic capture for runtime command receipts."""
from __future__ import annotations

import hashlib
from typing import Any

COMMAND_OUTPUT_LIMIT = 2000


def captured_runtime_streams(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    for name, raw in (("stdout", stdout), ("stderr", stderr)):
        try:
            text = raw.decode("utf-8")
            encoding_valid = True
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
            encoding_valid = False
        captured.update({
            name: _clip_stream(text, preserve_tail=name == "stderr"),
            f"{name}_truncated": len(text) > COMMAND_OUTPUT_LIMIT,
            f"{name}_encoding_valid": encoding_valid,
            f"{name}_bytes": len(raw),
            f"{name}_sha256": hashlib.sha256(raw).hexdigest(),
        })
    return captured


def stdout_capture_error(result: dict[str, Any]) -> tuple[str, str] | None:
    if result.get("stdout_truncated") is True:
        return "stdout_capture_incomplete", "runtime stdout contract cannot evaluate truncated output"
    if result.get("stdout_encoding_valid") is False:
        return "stdout_encoding_invalid", "runtime stdout contract requires valid UTF-8 output"
    if result.get("stdout_truncated") is not False or result.get("stdout_encoding_valid") is not True:
        return "stdout_capture_unverified", "runtime stdout contract has no verified lossless capture metadata"
    return None


def _clip_stream(text: str, *, preserve_tail: bool) -> str:
    if len(text) <= COMMAND_OUTPUT_LIMIT:
        return text
    if not preserve_tail:
        return text[:COMMAND_OUTPUT_LIMIT]
    head_limit = 400
    tail_limit = COMMAND_OUTPUT_LIMIT - head_limit - 32
    truncated = len(text) - head_limit - tail_limit
    return text[:head_limit] + f"\n...[truncated {truncated} chars]...\n" + text[-tail_limit:]
