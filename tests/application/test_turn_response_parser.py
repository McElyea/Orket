"""Layer: contract. Response parsing policy and stable artifact payloads."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_response_capture import capture_turn_response
from orket.application.workflows.turn_response_parser import ResponseParser

pytestmark = pytest.mark.asyncio
_NOW = datetime(2026, 9, 23, tzinfo=UTC)


class _Writer:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.writes: list[dict[str, Any]] = []

    def write_turn_artifact(self, **kwargs: Any) -> None:
        self.writes.append(kwargs)


@pytest.fixture
def parser_case(tmp_path: Path):
    writer = _Writer(tmp_path)
    destination = TurnArtifactDestination(
        writer=writer, workspace=tmp_path, session_id="s1", issue_id="ISSUE-1",
        role_name="coder", role_id="DEV", turn_index=1,
    )
    return ResponseParser(utc_now=lambda: _NOW), destination, writer.writes


async def _parse(parser_case, response: Any, context: dict[str, Any] | None = None):
    parser, destination, _ = parser_case
    return await parser.parse_response(
        response=capture_turn_response(response), destination=destination, context=context or {},
    )


async def test_response_parser_extracts_tool_calls(parser_case) -> None:
    """Layer: contract. Legacy content extraction retains its artifacts."""
    response = {
        "content": '{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
        "raw": {"total_tokens": 11},
    }
    turn = await _parse(parser_case, response)
    captured = parser_case[2]

    assert turn.issue_id == "ISSUE-1"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert turn.raw["extraction_strategy"] == "stack_json"
    assert captured and captured[0]["filename"] == "tool_parser_diagnostics.json"
    assert captured[1]["filename"] == "parsed_tool_calls.json"
    assert captured[2]["filename"] == "tool_parser_summary.json"
    assert json.loads(captured[2]["content"]) == {"extraction_strategy": "stack_json"}


async def test_response_parser_falls_back_to_native_tool_calls_when_content_is_empty(parser_case) -> None:
    """Layer: contract. Empty content uses captured provider-native calls."""
    response = SimpleNamespace(content="", raw={"tool_calls": [{
        "id": "call_1", "type": "function",
        "function": {"name": "write_file", "arguments": '{"path":"agent_output/main.py","content":"x"}'},
    }]})
    turn = await _parse(parser_case, response)
    captured = parser_case[2]

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert turn.tool_calls[0].args["path"] == "agent_output/main.py"
    assert turn.raw["extraction_strategy"] == "provider_native_tool_calls"
    assert captured[1]["filename"] == "parsed_tool_calls.json"
    assert "agent_output/main.py" in captured[1]["content"]
    assert captured[2]["filename"] == "tool_parser_summary.json"
    assert json.loads(captured[2]["content"]) == {"extraction_strategy": "provider_native_tool_calls"}


async def test_response_parser_marks_partial_recovery_failure_without_recovery_tool(parser_case) -> None:
    """Layer: contract. Partial recovery refuses executable calls."""
    response = {
        "content": ('```json\n{"tool":"write_file","args":{"path":"agent_output/main.py",'
                    '"content":"print(1)\\n"}}\n{"tool":"create_issue","args":{"title":"Ship it"}\n```'),
        "raw": {"total_tokens": 11},
    }
    turn = await _parse(parser_case, response)
    captured = parser_case[2]

    assert turn.tool_calls == []
    assert turn.partial_parse_failure is True
    assert turn.error_class is not None
    assert turn.error_class.value == "parse_partial"
    assert "tool-call recovery was partial" in (turn.error or "")
    diagnostics = captured[0]["content"]
    assert '"recovery_complete": false' in diagnostics
    parsed = captured[1]["content"]
    assert parsed.strip() == "[]"
    assert "write_file" not in parsed


async def test_response_parser_unwraps_legacy_args_wrapper_inside_native_tool_calls(parser_case) -> None:
    """Layer: contract. Provider-native legacy args wrappers remain accepted."""
    response = SimpleNamespace(content="", raw={"tool_calls": [{
        "id": "call_1", "type": "function", "function": {
            "name": "write_file", "arguments": '{"args":{"path":"agent_output/main.py","content":"x"}}',
        },
    }]})
    turn = await _parse(parser_case, response)

    assert turn.tool_calls[0].args == {"path": "agent_output/main.py", "content": "x"}


async def test_response_parser_filters_undeclared_native_tool_calls_and_dedupes_duplicates(parser_case) -> None:
    """Layer: contract. Native filtering and deduplication keep their policy."""
    def call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
        return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}

    response = SimpleNamespace(content="", raw={"tool_calls": [
        call("call_1", "read_file", '{"args":{"path":"agent_output/requirements.txt"}}'),
        call("call_2", "update_issue_status", '{"args":{"status":"done"}}'),
        call("call_3", "add_issue_comment", '{"args":{"comment":"extra"}}'),
        call("call_4", "update_issue_status", '{"args":{"status":"done"}}'),
    ]})
    turn = await _parse(parser_case, response, {
        "verification_scope": {"declared_interfaces": ["read_file", "update_issue_status"]},
    })

    assert [call.tool for call in turn.tool_calls] == ["read_file", "update_issue_status"]
    assert turn.tool_calls[0].args == {"path": "agent_output/requirements.txt"}
    assert turn.tool_calls[1].args == {"status": "done"}


async def test_response_parser_prefers_declared_native_tool_names_when_provider_telemetry_is_present(
    parser_case,
) -> None:
    """Layer: contract. Provider declarations retain precedence."""
    response = SimpleNamespace(content="", raw={
        "openai_native_tool_names": ["read_file"],
        "tool_calls": [
            {"id": "call_1", "type": "function", "function": {
                "name": "read_file", "arguments": '{"args":{"path":"agent_output/requirements.txt"}}',
            }},
            {"id": "call_2", "type": "function", "function": {
                "name": "update_issue_status", "arguments": '{"args":{"status":"done"}}',
            }},
        ],
    })
    turn = await _parse(parser_case, response, {
        "verification_scope": {"declared_interfaces": ["read_file", "update_issue_status"]},
    })

    assert [call.tool for call in turn.tool_calls] == ["read_file"]
    assert turn.tool_calls[0].args == {"path": "agent_output/requirements.txt"}


async def test_response_parser_non_json_residue_and_guard_payload(parser_case) -> None:
    """Layer: contract. Pure residue and guard parsing remain stable."""
    parser = parser_case[0]
    residue = parser.non_json_residue('{"tool":"read_file","args":{"path":"x"}} trailing')
    payload = parser.extract_guard_review_payload(
        "```json\n" '{"rationale":"ok","violations":[],"remediation_actions":[]}\n' "```"
    )

    assert residue == "trailing"
    assert payload.get("rationale") == "ok"


async def test_response_parser_non_json_residue_ignores_recovered_legacy_tool_only_payload(parser_case) -> None:
    """Layer: contract. Recovered tool-only content leaves no residue."""
    parser = parser_case[0]
    content = (
        '```json\n{\n  "tool": "write_file",\n  "args": {\n'
        '    "path": "agent_output/challenge_runtime/validator.py",\n'
        '    "content": "if task[\'duration\'] < 0:\\n    errors.append({\\n'
        '        \'message\': f\'Negative duration: {task["duration"]}\'\\n    })"\n  }\n}\n```\n\n'
        '```json\n{\n  "tool": "update_issue_status",\n'
        '  "args": {\n    "status": "code_review"\n  }\n}\n```'
    )
    residue = parser.non_json_residue(content)

    assert residue == ""


async def test_response_parser_strict_protocol_mode_accepts_canonical_envelope(parser_case) -> None:
    """Layer: contract. Strict canonical envelopes retain hash metadata."""
    response = {
        "content": '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"a.txt","content":"x"}}]}',
        "raw": {"total_tokens": 9},
    }
    turn = await _parse(parser_case, response, {"protocol_governed_enabled": True})

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert isinstance(turn.raw.get("proposal_hash"), str)
    assert len(turn.raw["proposal_hash"]) == 64
    assert isinstance(turn.raw.get("validator_version"), str)
    assert isinstance(turn.raw.get("protocol_hash"), str)
    assert isinstance(turn.raw.get("tool_schema_hash"), str)


async def test_response_parser_strict_protocol_mode_rejects_duplicate_keys(parser_case) -> None:
    """Layer: contract. Strict parsing refuses duplicate keys."""
    response = {"content": '{"content":"","tool_calls":[{"tool":"write_file","args":{},"args":{}}]}',
                "raw": {"total_tokens": 9}}
    with pytest.raises(ValueError) as raised:
        await _parse(parser_case, response, {"protocol_governed_enabled": True})
    assert "E_DUPLICATE_KEY" in str(raised.value)


async def test_response_parser_strict_protocol_mode_rejects_markdown_fences(parser_case) -> None:
    """Layer: contract. Strict parsing refuses outer markdown fences."""
    response = {"content": '```json\n{"content":"","tool_calls":[{"tool":"write_file","args":{}}]}\n```',
                "raw": {"total_tokens": 9}}
    with pytest.raises(ValueError) as raised:
        await _parse(parser_case, response, {"protocol_governed_enabled": True})
    assert "E_MARKDOWN_FENCE" in str(raised.value)


async def test_response_parser_strict_protocol_mode_allows_markdown_fence_inside_string_arg(parser_case) -> None:
    """Layer: contract. Fences inside string values remain data."""
    response = {
        "content": ('{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"README.md",'
                    '"content":"```sh\\npython main.py\\n```"}}]}'),
        "raw": {"total_tokens": 9},
    }
    turn = await _parse(parser_case, response, {"protocol_governed_enabled": True})

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].args["content"] == "```sh\npython main.py\n```"


async def test_response_parser_strict_protocol_mode_rejects_excess_tool_calls(parser_case) -> None:
    """Layer: contract. Strict parsing enforces the tool-call ceiling."""
    response = {
        "content": ('{"content":"","tool_calls":['
                    '{"tool":"write_file","args":{}},{"tool":"read_file","args":{}}]}'),
        "raw": {"total_tokens": 9},
    }
    with pytest.raises(ValueError) as raised:
        await _parse(parser_case, response, {"protocol_governed_enabled": True, "max_tool_calls": 1})
    assert "E_MAX_TOOL_CALLS" in str(raised.value)


async def test_response_parser_strict_protocol_mode_uses_context_overrides_for_hash_metadata(parser_case) -> None:
    """Layer: contract. Explicit hash metadata keeps precedence."""
    response = {
        "content": '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"a.txt","content":"x"}}]}',
        "raw": {"total_tokens": 9},
    }
    turn = await _parse(parser_case, response, {
        "protocol_governed_enabled": True, "validator_version": "turn-validator/custom",
        "protocol_hash": "p" * 64, "tool_schema_hash": "s" * 64,
    })
    assert turn.raw["validator_version"] == "turn-validator/custom"
    assert turn.raw["protocol_hash"] == "p" * 64
    assert turn.raw["tool_schema_hash"] == "s" * 64


async def test_response_parser_strips_leading_thinking_blocks_for_supported_formats(parser_case) -> None:
    """Layer: contract. Supported thinking blocks are stripped deterministically."""
    parser = parser_case[0]
    content = (
        "<think>first pass</think>\n<think>second pass</think>\n"
        '{"tool":"write_file","args":{"path":"a.txt","content":"x"}}'
    )
    stripped, count = parser.strip_leading_thinking_blocks(content, "xml_think_tags")

    assert count == 2
    assert stripped.strip().startswith('{"tool":"write_file"')


async def test_captured_dictionary_response_uses_the_entire_mapping(parser_case) -> None:
    """Layer: contract. Dictionary responses use the full mapping as raw."""
    response = {"content": "plain response", "raw": {"total_tokens": 99}, "total_tokens": 7}
    captured = capture_turn_response(response)
    turn = await parser_case[0].parse_response(
        response=captured, destination=parser_case[1], context={},
    )

    assert json.loads(captured.raw_artifact_content) == response
    assert turn.tokens_used == 7
    assert turn.raw["raw"] == {"total_tokens": 99}


async def test_captured_non_dictionary_raw_keeps_artifact_value_and_parser_empty_mapping(parser_case) -> None:
    """Layer: contract. Non-mapping raw values remain artifact-only."""
    response = SimpleNamespace(content="plain response", raw=["provider", {"value": 3}])
    captured = capture_turn_response(response)
    turn = await parser_case[0].parse_response(
        response=captured, destination=parser_case[1], context={},
    )

    assert json.loads(captured.raw_artifact_content) == response.raw
    assert turn.tokens_used == 0
    assert turn.raw == {"extraction_strategy": "none"}


async def test_capture_detaches_named_inputs_before_rendering_borrowed_extensions(parser_case) -> None:
    """Layer: contract. Extension rendering cannot rewrite captured parser inputs."""
    raw_call = {"function": {"name": "read_file", "arguments": '{"path":"a.txt"}'}}

    class _MutatingExtension:
        def __str__(self) -> str:
            raw_call["function"]["name"] = "write_file"
            raw["openai_native_tool_names"][0] = "write_file"
            return "rendered extension"

    raw = {
        "extension": _MutatingExtension(),
        "tool_calls": [raw_call],
        "openai_native_tool_names": ["read_file"],
    }
    captured = capture_turn_response(SimpleNamespace(content="", raw=raw))
    turn = await parser_case[0].parse_response(
        response=captured, destination=parser_case[1], context={},
    )

    assert json.loads(captured.raw_artifact_content)["tool_calls"][0]["function"]["name"] == "read_file"
    assert [(call.tool, call.args) for call in turn.tool_calls] == [("read_file", {"path": "a.txt"})]
    assert raw_call["function"]["name"] == "write_file"


async def test_legacy_parsing_ignores_unused_strict_policy_values(parser_case) -> None:
    """Layer: contract. Legacy parsing does not normalize strict-only policy."""
    class _InvalidStrictValue:
        def __int__(self) -> int:
            raise AssertionError("unused strict limit was normalized")

        def __str__(self) -> str:
            raise AssertionError("unused strict hash was normalized")

    unused = _InvalidStrictValue()
    turn = await _parse(parser_case, {
        "content": '{"tool":"read_file","args":{"path":"a.txt"}}', "raw": {},
    }, {
        "max_response_bytes": unused, "max_tool_calls": unused,
        "validator_version": unused, "protocol_hash": unused, "tool_schema_hash": unused,
    })

    assert [(call.tool, call.args) for call in turn.tool_calls] == [("read_file", {"path": "a.txt"})]


async def test_strict_parsing_ignores_unused_native_policy_values(parser_case) -> None:
    """Layer: contract. Strict parsing does not normalize native fallback policy."""
    class _InvalidNativeName:
        def __str__(self) -> str:
            raise AssertionError("unused native name was normalized")

    turn = await _parse(parser_case, {
        "content": '{"content":"","tool_calls":[{"tool":"read_file","args":{}}]}', "raw": {},
    }, {
        "protocol_governed_enabled": True,
        "required_action_tools": [_InvalidNativeName()],
    })

    assert [call.tool for call in turn.tool_calls] == ["read_file"]


async def test_native_fallback_normalizes_captured_required_tools_when_consumed(parser_case) -> None:
    """Layer: contract. Native fallback resolves its captured policy on demand."""
    class _NativeName:
        def __str__(self) -> str:
            return "read_file"

    response = SimpleNamespace(content="", raw={"tool_calls": [{
        "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'},
    }]})
    turn = await _parse(parser_case, response, {"required_action_tools": [_NativeName()]})

    assert [(call.tool, call.args) for call in turn.tool_calls] == [("read_file", {"path": "a.txt"})]
