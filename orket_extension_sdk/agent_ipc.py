from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from .agent_models import AgentStdioFrame
from .agent_validation import MAX_AGENT_WIRE_BYTES, validate_governed_agent_payload
from .controller import canonical_json

_HEADER_BYTES = 4


def encode_agent_frame(frame: AgentStdioFrame | Mapping[str, Any]) -> bytes:
    payload = frame.to_wire() if isinstance(frame, AgentStdioFrame) else dict(frame)
    validate_governed_agent_payload(payload)
    encoded = cast(str, canonical_json(payload)).encode("utf-8")
    if len(encoded) > MAX_AGENT_WIRE_BYTES:
        raise ValueError("E_SDK_AGENT_FRAME_TOO_LARGE")
    return struct.pack(">I", len(encoded)) + encoded


def decode_agent_frame(data: bytes) -> AgentStdioFrame:
    if len(data) < _HEADER_BYTES:
        raise ValueError("E_SDK_AGENT_FRAME_HEADER_INCOMPLETE")
    payload_length = struct.unpack(">I", data[:_HEADER_BYTES])[0]
    if payload_length > MAX_AGENT_WIRE_BYTES:
        raise ValueError("E_SDK_AGENT_FRAME_TOO_LARGE")
    if len(data) != _HEADER_BYTES + payload_length:
        raise ValueError("E_SDK_AGENT_FRAME_LENGTH_MISMATCH")
    try:
        payload = json.loads(data[_HEADER_BYTES:].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("E_SDK_AGENT_FRAME_UTF8_INVALID") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("E_SDK_AGENT_FRAME_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ValueError("E_SDK_AGENT_FRAME_OBJECT_REQUIRED")
    return AgentStdioFrame.from_wire(payload)


async def read_agent_frame(reader: asyncio.StreamReader, *, timeout_seconds: float) -> AgentStdioFrame:
    if timeout_seconds <= 0:
        raise ValueError("E_SDK_AGENT_FRAME_TIMEOUT_INVALID")
    try:
        header = await asyncio.wait_for(reader.readexactly(_HEADER_BYTES), timeout=timeout_seconds)
        payload_length = struct.unpack(">I", header)[0]
        if payload_length > MAX_AGENT_WIRE_BYTES:
            raise ValueError("E_SDK_AGENT_FRAME_TOO_LARGE")
        payload = await asyncio.wait_for(reader.readexactly(payload_length), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise ValueError("E_SDK_AGENT_FRAME_READ_TIMEOUT") from exc
    except asyncio.IncompleteReadError as exc:
        raise ValueError("E_SDK_AGENT_FRAME_INCOMPLETE") from exc
    return await asyncio.to_thread(decode_agent_frame, header + payload)


async def write_agent_frame(writer: asyncio.StreamWriter, frame: AgentStdioFrame) -> None:
    encoded = await asyncio.to_thread(encode_agent_frame, frame)
    writer.write(encoded)
    await writer.drain()


@dataclass(slots=True)
class AgentFrameSequenceValidator:
    """Validate retained invocation, direction, sequence, and terminal framing."""

    invocation_id: str
    direction: Literal["parent_to_child", "child_to_parent"]
    _next_sequence: int = 1
    _terminal_seen: bool = False
    _bootstrap_or_ready_seen: bool = False

    def accept(self, frame: AgentStdioFrame) -> None:
        if frame.invocation_id != self.invocation_id:
            raise ValueError("E_SDK_AGENT_FRAME_INVOCATION_MISMATCH")
        if frame.direction != self.direction:
            raise ValueError("E_SDK_AGENT_FRAME_DIRECTION_INVALID")
        if self._terminal_seen:
            raise ValueError("E_SDK_AGENT_FRAME_AFTER_TERMINAL")
        if frame.sequence != self._next_sequence:
            raise ValueError("E_SDK_AGENT_FRAME_SEQUENCE_INVALID")
        first_type = "bootstrap" if self.direction == "parent_to_child" else "ready"
        if not self._bootstrap_or_ready_seen and frame.message_type != first_type:
            raise ValueError(f"E_SDK_AGENT_FRAME_{first_type.upper()}_REQUIRED")
        if self._bootstrap_or_ready_seen and frame.message_type == first_type:
            raise ValueError(f"E_SDK_AGENT_FRAME_{first_type.upper()}_DUPLICATE")
        self._bootstrap_or_ready_seen = True
        self._next_sequence += 1
        if frame.message_type in {"iteration_result", "cancel"}:
            self._terminal_seen = True
