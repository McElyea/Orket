from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.application.services.tool_parser import ToolParser
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event
from orket.runtime.protocol_error_codes import (
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

from .protocol_hashing import VALIDATOR_VERSION, default_protocol_hash, default_tool_schema_hash, hash_canonical_json


class ResponseParser:
    """Model response parsing and JSON residue helpers for turn execution."""

    def __init__(self, workspace: Path, write_turn_artifact: Callable[..., None]) -> None:
        self.workspace = workspace
        self.write_turn_artifact = write_turn_artifact

    def parse_response(
        self,
        *,
        response: Any,
        issue_id: str,
        role_name: str,
        context: dict[str, Any],
    ) -> ExecutionTurn:
        content = getattr(response, "content", "") if not isinstance(response, dict) else response.get("content", "")
        raw_data = getattr(response, "raw", {}) if not isinstance(response, dict) else response
        raw_payload = dict(raw_data) if isinstance(raw_data, dict) else {}
        protocol_metadata: dict[str, Any] = {}

        parser_diag: list[dict[str, Any]] = []

        def capture(stage: str, data: dict[str, Any]) -> None:
            parser_diag.append({"stage": stage, "data": data})

        if bool(context.get("protocol_governed_enabled", False)):
            envelope = self._parse_strict_envelope(
                content=content,
                max_response_bytes=int(context.get("max_response_bytes", 8192)),
                max_tool_calls=int(context.get("max_tool_calls", 8)),
            )
            proposal_hash = hash_canonical_json(envelope)
            protocol_metadata = {
                "proposal_hash": proposal_hash,
                "validator_version": str(context.get("validator_version") or VALIDATOR_VERSION),
                "protocol_hash": str(context.get("protocol_hash") or default_protocol_hash()),
                "tool_schema_hash": str(context.get("tool_schema_hash") or default_tool_schema_hash()),
            }
            capture("strict_parse_success", {"tool_call_count": len(envelope["tool_calls"])})
            parsed_calls = list(envelope["tool_calls"])
            content = envelope["content"]
        else:
            parsed_calls = ToolParser.parse(content, diagnostics=capture)
            parsed_calls = self._fail_closed_on_partial_recovery(
                parsed_calls=parsed_calls,
                parser_diag=parser_diag,
                issue_id=issue_id,
                role_name=role_name,
                context=context,
            )
            if not parsed_calls:
                parsed_calls = self._parse_native_tool_calls(
                    raw_payload,
                    diagnostics=capture,
                    allowed_tool_names=self._allowed_native_tool_names(context, raw_payload),
                )
        if protocol_metadata:
            raw_payload.update(protocol_metadata)
        session_id = context.get("session_id", "unknown-session")
        turn_index = int(context.get("turn_index", 0))
        for diag in parser_diag:
            log_event(
                "tool_parser_diagnostic",
                {
                    "issue_id": issue_id,
                    "role": role_name,
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "stage": diag["stage"],
                    "details": diag["data"],
                },
                self.workspace,
            )
        self.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="tool_parser_diagnostics.json",
            content=json.dumps(parser_diag, indent=2, ensure_ascii=False),
        )
        self.write_turn_artifact(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            filename="parsed_tool_calls.json",
            content=json.dumps(parsed_calls, indent=2, ensure_ascii=False),
        )

        tool_calls = [
            ToolCall(
                tool=parsed_call.get("tool"),
                args=parsed_call.get("args", {}),
                result=None,
                error=None,
            )
            for parsed_call in parsed_calls
        ]
        return ExecutionTurn(
            role=role_name,
            issue_id=issue_id,
            thought=None,
            content=content,
            tool_calls=tool_calls,
            tokens_used=raw_payload.get("total_tokens", 0),
            timestamp=datetime.now(UTC),
            raw=raw_payload,
        )

    def _allowed_native_tool_names(self, context: dict[str, Any], raw_payload: dict[str, Any]) -> set[str]:
        declared_native_tool_names = raw_payload.get("openai_native_tool_names")
        if isinstance(declared_native_tool_names, list):
            return {
                str(item).strip()
                for item in declared_native_tool_names
                if str(item).strip()
            }
        verification_scope = context.get("verification_scope")
        declared_interfaces = (
            verification_scope.get("declared_interfaces")
            if isinstance(verification_scope, dict)
            else None
        )
        allowed = {
            str(item).strip()
            for item in (declared_interfaces or context.get("required_action_tools") or [])
            if str(item).strip()
        }
        return allowed

    def _fail_closed_on_partial_recovery(
        self,
        *,
        parsed_calls: list[dict[str, Any]],
        parser_diag: list[dict[str, Any]],
        issue_id: str,
        role_name: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        partial_events = [
            dict(item.get("data") or {})
            for item in parser_diag
            if item.get("stage") == "parse_partial_recovery"
            and dict(item.get("data") or {}).get("recovery_complete") is False
        ]
        if not partial_events:
            return parsed_calls

        skipped_tools: list[dict[str, str]] = []
        for event in partial_events:
            skipped_tools.extend(
                dict(item)
                for item in (event.get("skipped_tools") or [])
                if isinstance(item, dict)
            )
        session_id = str(context.get("session_id", "unknown-session"))
        turn_index = int(context.get("turn_index", 0))
        log_event(
            "tool_recovery_partial",
            {
                "issue_id": issue_id,
                "role": role_name,
                "session_id": session_id,
                "turn_index": turn_index,
                "recovered_count": len(parsed_calls),
                "skipped_tools": skipped_tools,
                "result": "blocked",
            },
            self.workspace,
        )
        comment = (
            "Blocked: tool-call recovery was partial, so Orket did not execute the recovered tool calls. "
            f"Skipped tools: {json.dumps(skipped_tools, ensure_ascii=False)}"
        )
        return [{"tool": "add_issue_comment", "args": {"comment": comment}}]

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
        blob = content or ""
        decoder = json.JSONDecoder()
        candidates: list[dict[str, Any]] = []

        fenced_matches = re.findall(r"```json\s*([\s\S]*?)```", blob, flags=re.IGNORECASE)
        for chunk in fenced_matches:
            try:
                parsed = json.loads(chunk.strip())
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        start = 0
        while True:
            brace_index = blob.find("{", start)
            if brace_index == -1:
                break
            try:
                parsed, end_pos = decoder.raw_decode(blob[brace_index:])
                if isinstance(parsed, dict):
                    candidates.append(parsed)
                start = brace_index + max(end_pos, 1)
            except json.JSONDecodeError:
                start = brace_index + 1

        for parsed in candidates:
            if {"rationale", "violations", "remediation_actions"} & set(parsed.keys()):
                return parsed
        return {}


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _DuplicateKeyError(key)
        payload[key] = value
    return payload
