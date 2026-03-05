from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from pathlib import Path
from typing import Any, Callable

from orket.application.services.tool_parser import ToolParser
from orket.domain.execution import ExecutionTurn, ToolCall
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
        if "```" in trimmed:
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
        return "".join(kept).strip()

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
