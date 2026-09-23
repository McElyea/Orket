from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.guard_review_payload import extract_legacy_guard_review
from orket.application.services.tool_parser import ToolParser
from orket.core.contracts.protocol_error_codes import (
    E_DUPLICATE_KEY_PREFIX,
    E_MARKDOWN_FENCE,
    E_MAX_TOOL_CALLS_PREFIX,
    E_MISSING_TOOL_CALLS,
    E_NON_ASCII_WHITESPACE,
    E_PARSE_JSON,
    E_RESPONSE_BYTES,
    E_SCHEMA_ENVELOPE,
    E_SCHEMA_TOOL_CALL_PREFIX,
    E_TOOL_MODE_CONTENT_NON_EMPTY,
    format_protocol_error,
)
from orket.core.domain.execution import ExecutionTurn, ToolCallErrorClass
from orket.logging import log_event

from .turn_artifact_destination import TurnArtifactDestination
from .turn_response_capture import CapturedTurnResponse
from .turn_response_parser_operation import capture_parser_policy, parse_and_publish_response


class ResponseParser:
    """Model response parsing and JSON residue helpers for turn execution."""

    def __init__(self, *, utc_now: Callable[[], datetime]) -> None:
        self.utc_now = utc_now

    async def parse_response(
        self,
        *,
        response: CapturedTurnResponse,
        destination: TurnArtifactDestination,
        context: dict[str, Any],
    ) -> ExecutionTurn:
        policy = capture_parser_policy(context=context)
        return await run_owned_thread(
            partial(
                parse_and_publish_response,
                parser=self,
                response=response,
                destination=destination,
                policy=policy,
                utc_now=self.utc_now,
            ),
            label="turn-response-parser",
        )

    def _parser_extraction_strategy(self, parser_diag: list[dict[str, Any]]) -> str:
        for diag in reversed(parser_diag):
            if diag.get("stage") != "parse_success":
                continue
            data = diag.get("data")
            if isinstance(data, dict):
                strategy = str(data.get("strategy") or "").strip()
                if strategy:
                    return strategy
        return "none"

    def _partial_recovery_error(
        self,
        *,
        parsed_calls: list[dict[str, Any]],
        parser_diag: list[dict[str, Any]],
        destination: TurnArtifactDestination,
    ) -> dict[str, Any] | None:
        partial_events = [
            dict(item.get("data") or {})
            for item in parser_diag
            if item.get("stage") == "parse_partial_recovery"
            and dict(item.get("data") or {}).get("recovery_complete") is False
        ]
        if not partial_events:
            return None

        skipped_tools: list[dict[str, str]] = []
        for event in partial_events:
            skipped_tools.extend(
                dict(item)
                for item in (event.get("skipped_tools") or [])
                if isinstance(item, dict)
            )
        log_event(
            "tool_recovery_partial",
            {
                "issue_id": destination.issue_id,
                "role": destination.role_name,
                "session_id": destination.session_id,
                "turn_index": destination.turn_index,
                "recovered_count": len(parsed_calls),
                "skipped_tools": skipped_tools,
                "result": "blocked",
            },
            destination.workspace,
        )
        return {
            "error": "tool-call recovery was partial; Orket did not execute recovered or skipped tool calls",
            "error_class": ToolCallErrorClass.PARSE_PARTIAL.value,
            "recovered_count": len(parsed_calls),
            "skipped_tools": skipped_tools,
        }

    def _parse_native_tool_calls(
        self,
        raw_payload: dict[str, Any],
        *,
        diagnostics: Callable[[str, dict[str, Any]], None],
        allowed_tool_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        native_calls = raw_payload.get("tool_calls")
        if not isinstance(native_calls, list) or not native_calls:
            return []
        normalized: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        for index, item in enumerate(native_calls):
            if not isinstance(item, dict):
                diagnostics("native_tool_call_skipped", {"index": index, "reason": "non_object"})
                continue
            function_payload = item.get("function")
            if not isinstance(function_payload, dict):
                diagnostics("native_tool_call_skipped", {"index": index, "reason": "missing_function"})
                continue
            tool_name = str(function_payload.get("name") or "").strip()
            if not tool_name:
                diagnostics("native_tool_call_skipped", {"index": index, "reason": "missing_name"})
                continue
            if allowed_tool_names and tool_name not in allowed_tool_names:
                diagnostics(
                    "native_tool_call_skipped",
                    {"index": index, "reason": "undeclared_tool", "tool": tool_name},
                )
                continue
            arguments = function_payload.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    diagnostics("native_tool_call_skipped", {"index": index, "reason": "invalid_arguments_json"})
                    continue
            if not isinstance(arguments, dict):
                diagnostics("native_tool_call_skipped", {"index": index, "reason": "arguments_not_object"})
                continue
            if set(arguments.keys()) == {"args"} and isinstance(arguments.get("args"), dict):
                arguments = dict(arguments["args"])
            signature = json.dumps({"tool": tool_name, "args": arguments}, ensure_ascii=False, sort_keys=True)
            if signature in seen_signatures:
                diagnostics(
                    "native_tool_call_skipped",
                    {"index": index, "reason": "duplicate_tool_call", "tool": tool_name},
                )
                continue
            seen_signatures.add(signature)
            normalized.append({"tool": tool_name, "args": arguments})
        if normalized:
            diagnostics("native_tool_calls_success", {"tool_call_count": len(normalized)})
        return normalized

    def _parse_strict_envelope(
        self,
        *,
        content: Any,
        max_response_bytes: int,
        max_tool_calls: int,
    ) -> dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError(format_protocol_error(E_PARSE_JSON, "response content must be a string"))
        payload_bytes = content.encode("utf-8")
        if len(payload_bytes) > max(1, int(max_response_bytes)):
            raise ValueError(E_RESPONSE_BYTES)
        trimmed = self._trim_ascii_whitespace_once(content)
        if self._contains_markdown_fence_outside_json_strings(trimmed):
            raise ValueError(E_MARKDOWN_FENCE)
        try:
            parsed = json.loads(trimmed, object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateKeyError as exc:
            raise ValueError(format_protocol_error(E_DUPLICATE_KEY_PREFIX, str(exc))) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(E_PARSE_JSON) from exc

        if not isinstance(parsed, dict):
            raise ValueError(E_SCHEMA_ENVELOPE)
        if set(parsed.keys()) != {"content", "tool_calls"}:
            raise ValueError(E_SCHEMA_ENVELOPE)
        if not isinstance(parsed.get("content"), str):
            raise ValueError(E_SCHEMA_ENVELOPE)
        if not isinstance(parsed.get("tool_calls"), list):
            raise ValueError(E_SCHEMA_ENVELOPE)
        if parsed.get("content") != "":
            raise ValueError(E_TOOL_MODE_CONTENT_NON_EMPTY)
        tool_calls: list[dict[str, Any]] = []
        for index, item in enumerate(parsed["tool_calls"]):
            if not isinstance(item, dict):
                raise ValueError(format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, str(index)))
            if set(item.keys()) != {"tool", "args"}:
                raise ValueError(format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, str(index)))
            tool_name = item.get("tool")
            args = item.get("args")
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise ValueError(format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, str(index)))
            if not isinstance(args, dict):
                raise ValueError(format_protocol_error(E_SCHEMA_TOOL_CALL_PREFIX, str(index)))
            tool_calls.append({"tool": tool_name, "args": args})
        if not tool_calls:
            raise ValueError(E_MISSING_TOOL_CALLS)
        if len(tool_calls) > max(1, int(max_tool_calls)):
            raise ValueError(format_protocol_error(E_MAX_TOOL_CALLS_PREFIX, str(len(tool_calls))))
        return {"content": "", "tool_calls": tool_calls}

    def _contains_markdown_fence_outside_json_strings(self, content: str) -> bool:
        in_string = False
        escaped = False
        for index, char in enumerate(content):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if content[index : index + 3] == "```":
                return True
        return False

    def _trim_ascii_whitespace_once(self, content: str) -> str:
        allowed = {" ", "\t", "\n", "\r"}
        if content and content[0].isspace() and content[0] not in allowed:
            raise ValueError(E_NON_ASCII_WHITESPACE)
        if content and content[-1].isspace() and content[-1] not in allowed:
            raise ValueError(E_NON_ASCII_WHITESPACE)
        start = 0
        end = len(content)
        while start < end and content[start] in allowed:
            start += 1
        while end > start and content[end - 1] in allowed:
            end -= 1
        return content[start:end]

    def strip_leading_thinking_blocks(self, content: str, thinking_block_format: str = "none") -> tuple[str, int]:
        format_token = str(thinking_block_format or "").strip().lower().replace("-", "_")
        if format_token not in {"xml_think_tags", "provider_native"}:
            return str(content or ""), 0

        working = str(content or "")
        consumed = 0
        while True:
            trimmed = working.lstrip(" \t\r\n")
            opening = re.match(r"<\s*think\b[^>]*>", trimmed, flags=re.IGNORECASE)
            if opening is None:
                break
            trailing = trimmed[opening.end() :]
            closing = re.search(r"<\s*/\s*think\s*>", trailing, flags=re.IGNORECASE)
            if closing is None:
                break
            working = trailing[closing.end() :]
            consumed += 1
        return working, consumed

    def non_json_residue(self, content: str) -> str:
        blob = ToolParser.normalize_json_stringify(content or "")
        blob = re.sub(r"```(?:json)?", " ", blob, flags=re.IGNORECASE)
        if not blob.strip():
            return ""
        decoder = json.JSONDecoder()
        kept: list[str] = []
        idx = 0
        n = len(blob)
        while idx < n:
            ch = blob[idx]
            if ch.isspace():
                idx += 1
                continue
            if ch in {"{", "["}:
                try:
                    parsed, end_pos = decoder.raw_decode(blob[idx:])
                    if isinstance(parsed, dict):
                        idx += max(end_pos, 1)
                        continue
                    if isinstance(parsed, list):
                        if all(isinstance(item, dict) for item in parsed):
                            idx += max(end_pos, 1)
                            continue
                        kept.append(ch)
                        idx += 1
                        continue
                    idx += max(end_pos, 1)
                    continue
                except json.JSONDecodeError:
                    kept.append(ch)
                    idx += 1
                    continue
            if ch == ",":
                lookahead = idx + 1
                while lookahead < n and blob[lookahead].isspace():
                    lookahead += 1
                if lookahead < n and blob[lookahead] == "{":
                    idx += 1
                    continue
            kept.append(ch)
            idx += 1
        residue = "".join(kept).strip()
        if residue and self._is_legacy_tool_only_residue(blob, residue):
            return ""
        return residue

    def _is_legacy_tool_only_residue(self, blob: str, residue: str) -> bool:
        stripped = str(blob or "").strip()
        compare_residue = re.sub(r"[\s,\[\]]+", "", str(residue or ""))
        if not stripped or not compare_residue.startswith('{"tool"'):
            return False

        parsed_calls = ToolParser.parse(stripped)
        if not parsed_calls:
            return False

        marker_pattern = re.compile(r'"tool"\s*:\s*"[a-zA-Z0-9_]+"')
        tool_markers = list(marker_pattern.finditer(stripped))
        if len(tool_markers) != len(parsed_calls):
            return False

        object_starts: list[int] = []
        for marker in tool_markers:
            object_start = stripped.rfind("{", 0, marker.start())
            if object_start == -1:
                return False
            object_starts.append(object_start)

        prefix = stripped[: object_starts[0]]
        if prefix.strip():
            return False

        for index, start in enumerate(object_starts):
            next_start = object_starts[index + 1] if index + 1 < len(object_starts) else len(stripped)
            compare_segment = re.sub(r"[\s,\[\]]+", "", stripped[start:next_start]).rstrip(",")
            if not compare_segment.startswith('{"tool"'):
                continue
            if not compare_segment.endswith("}"):
                continue
            if compare_segment == compare_residue:
                return True
        return False

    def extract_guard_review_payload(self, content: str) -> dict[str, Any]:
        return extract_legacy_guard_review(content)


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _DuplicateKeyError(key)
        payload[key] = value
    return payload
