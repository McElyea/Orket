from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from orket.application.services.tool_parser import ToolParser
from orket.core.contracts.protocol_hashing import (
    VALIDATOR_VERSION,
    default_protocol_hash,
    default_tool_schema_hash,
    hash_canonical_json,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall, ToolCallErrorClass
from orket.logging import log_event

from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import capture_mapping
from .turn_response_capture import CapturedTurnResponse

if TYPE_CHECKING:
    from .turn_response_parser import ResponseParser


@dataclass(frozen=True, slots=True)
class ParserPolicyInputs:
    protocol_governed_enabled: Any
    max_response_bytes: Any
    max_tool_calls: Any
    validator_version: Any
    protocol_hash: Any
    tool_schema_hash: Any
    declared_interfaces: Any
    required_action_tools: Any


@dataclass(slots=True)
class _ParsedResponse:
    content: Any
    raw_payload: dict[str, Any]
    parsed_calls: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    extraction_strategy: str
    partial_error: dict[str, Any] | None


def capture_parser_policy(*, context: dict[str, Any]) -> ParserPolicyInputs:
    verification_scope = context.get("verification_scope")
    captured = capture_mapping({
        "protocol_governed_enabled": context.get("protocol_governed_enabled", False),
        "max_response_bytes": context.get("max_response_bytes", 8192),
        "max_tool_calls": context.get("max_tool_calls", 8),
        "validator_version": context.get("validator_version"),
        "protocol_hash": context.get("protocol_hash"),
        "tool_schema_hash": context.get("tool_schema_hash"),
        "declared_interfaces": (
            verification_scope.get("declared_interfaces")
            if isinstance(verification_scope, dict)
            else None
        ),
        "required_action_tools": context.get("required_action_tools"),
    })
    return ParserPolicyInputs(
        protocol_governed_enabled=captured["protocol_governed_enabled"],
        max_response_bytes=captured["max_response_bytes"],
        max_tool_calls=captured["max_tool_calls"],
        validator_version=captured["validator_version"],
        protocol_hash=captured["protocol_hash"],
        tool_schema_hash=captured["tool_schema_hash"],
        declared_interfaces=captured["declared_interfaces"],
        required_action_tools=captured["required_action_tools"],
    )


def parse_and_publish_response(
    *, parser: ResponseParser, response: CapturedTurnResponse, destination: TurnArtifactDestination,
    policy: ParserPolicyInputs, utc_now: Callable[[], datetime],
) -> ExecutionTurn:
    parsed = _parse_response(parser=parser, response=response, destination=destination, policy=policy)
    contents = _render_artifacts(parsed)
    _log_diagnostics(parsed.diagnostics, destination)
    for filename, content in contents:
        destination.writer.write_turn_artifact(destination=destination, filename=filename, content=content)
    return _build_turn(parsed=parsed, destination=destination, utc_now=utc_now)


def _parse_response(
    *, parser: ResponseParser, response: CapturedTurnResponse, destination: TurnArtifactDestination,
    policy: ParserPolicyInputs,
) -> _ParsedResponse:
    content, raw_payload = response.content, dict(response.raw_payload)
    diagnostics: list[dict[str, Any]] = []

    def capture(stage: str, data: dict[str, Any]) -> None:
        diagnostics.append({"stage": stage, "data": data})

    partial_error: dict[str, Any] | None = None
    if bool(policy.protocol_governed_enabled):
        envelope = parser._parse_strict_envelope(
            content=content, max_response_bytes=int(policy.max_response_bytes),
            max_tool_calls=int(policy.max_tool_calls),
        )
        raw_payload.update(
            proposal_hash=hash_canonical_json(envelope),
            validator_version=str(policy.validator_version or VALIDATOR_VERSION),
            protocol_hash=str(policy.protocol_hash or default_protocol_hash()),
            tool_schema_hash=str(policy.tool_schema_hash or default_tool_schema_hash()),
        )
        capture("strict_parse_success", {"tool_call_count": len(envelope["tool_calls"])})
        parsed_calls, content, strategy = list(envelope["tool_calls"]), envelope["content"], "strict_envelope"
    else:
        parsed_calls = ToolParser.parse(content, diagnostics=capture)
        strategy = parser._parser_extraction_strategy(diagnostics)
        partial_error = parser._partial_recovery_error(
            parsed_calls=parsed_calls, parser_diag=diagnostics, destination=destination,
        )
        if partial_error is not None:
            parsed_calls = []
        elif not parsed_calls:
            parsed_calls = parser._parse_native_tool_calls(
                raw_payload, diagnostics=capture,
                allowed_tool_names=_allowed_native_tool_names(raw_payload, policy),
            )
            strategy = "provider_native_tool_calls" if parsed_calls else "none"
    raw_payload["extraction_strategy"] = strategy
    if partial_error is not None:
        raw_payload["partial_parse_failure"] = partial_error
    return _ParsedResponse(content, raw_payload, parsed_calls, diagnostics, strategy, partial_error)


def _render_artifacts(parsed: _ParsedResponse) -> tuple[tuple[str, str], ...]:
    return (
        ("tool_parser_diagnostics.json", json.dumps(parsed.diagnostics, indent=2, ensure_ascii=False)),
        ("parsed_tool_calls.json", json.dumps(parsed.parsed_calls, indent=2, ensure_ascii=False)),
        ("tool_parser_summary.json", json.dumps(
            {"extraction_strategy": parsed.extraction_strategy}, indent=2, ensure_ascii=False,
        )),
    )


def _allowed_native_tool_names(
    raw_payload: dict[str, Any], policy: ParserPolicyInputs,
) -> set[str]:
    declared_native_tool_names = raw_payload.get("openai_native_tool_names")
    if isinstance(declared_native_tool_names, list):
        return {
            str(item).strip()
            for item in declared_native_tool_names
            if str(item).strip()
        }
    return {
        str(item).strip()
        for item in (policy.declared_interfaces or policy.required_action_tools or [])
        if str(item).strip()
    }


def _log_diagnostics(diagnostics: list[dict[str, Any]], destination: TurnArtifactDestination) -> None:
    for diagnostic in diagnostics:
        log_event("tool_parser_diagnostic", {
            "issue_id": destination.issue_id, "role": destination.role_name,
            "session_id": destination.session_id, "turn_index": destination.turn_index,
            "stage": diagnostic["stage"], "details": diagnostic["data"],
        }, destination.workspace)


def _build_turn(
    *, parsed: _ParsedResponse, destination: TurnArtifactDestination,
    utc_now: Callable[[], datetime],
) -> ExecutionTurn:
    partial = parsed.partial_error
    tool_calls = [
        ToolCall(tool=item.get("tool"), args=item.get("args", {}), result=None, error=None)
        for item in parsed.parsed_calls
    ]
    return ExecutionTurn(
        role=destination.role_name, issue_id=destination.issue_id, thought=None, content=parsed.content,
        tool_calls=tool_calls, tokens_used=parsed.raw_payload.get("total_tokens", 0),
        timestamp=utc_now(), raw=parsed.raw_payload,
        partial_parse_failure=partial is not None,
        error=None if partial is None else str(partial["error"]),
        error_class=ToolCallErrorClass.PARSE_PARTIAL if partial else None,
    )


__all__ = ["ParserPolicyInputs", "capture_parser_policy", "parse_and_publish_response"]
