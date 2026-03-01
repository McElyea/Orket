from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from pathlib import Path
from typing import Any, Callable

from orket.application.services.tool_parser import ToolParser
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.logging import log_event


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

        parser_diag: list[dict[str, Any]] = []

        def capture(stage: str, data: dict[str, Any]) -> None:
            parser_diag.append({"stage": stage, "data": data})

        parsed_calls = ToolParser.parse(content, diagnostics=capture)
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
            tokens_used=raw_data.get("total_tokens", 0),
            timestamp=datetime.now(UTC),
            raw=raw_data,
        )

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
