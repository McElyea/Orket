from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from orket.application.workflows.turn_response_parser import ResponseParser


def test_response_parser_extracts_tool_calls(tmp_path: Path) -> None:
    captured: list[dict] = []

    def _write_turn_artifact(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)

    parser = ResponseParser(tmp_path, _write_turn_artifact)
    response = {
        "content": '{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
        "raw": {"total_tokens": 11},
    }
    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1},
    )

    assert turn.issue_id == "ISSUE-1"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert captured and captured[0]["filename"] == "tool_parser_diagnostics.json"
    assert captured[1]["filename"] == "parsed_tool_calls.json"


def test_response_parser_falls_back_to_native_tool_calls_when_content_is_empty(tmp_path: Path) -> None:
    """Layer: contract. Verifies empty-content responses still parse provider-native tool calls."""
    captured: list[dict] = []

    def _write_turn_artifact(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)

    parser = ResponseParser(tmp_path, _write_turn_artifact)
    response = SimpleNamespace(
        content="",
        raw={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": '{"path":"agent_output/main.py","content":"x"}'},
                }
            ]
        },
    )

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1},
    )

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert turn.tool_calls[0].args["path"] == "agent_output/main.py"
    assert captured[1]["filename"] == "parsed_tool_calls.json"
    assert "agent_output/main.py" in captured[1]["content"]


def test_response_parser_replaces_partial_recovery_with_blocked_comment(tmp_path: Path) -> None:
    """Layer: contract. Verifies partial tool recovery does not execute recovered calls silently."""
    captured: list[dict] = []

    def _write_turn_artifact(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)

    parser = ResponseParser(tmp_path, _write_turn_artifact)
    response = {
        "content": (
            '```json\n'
            '{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)\\n"}}\n'
            '{"tool":"create_issue","args":{"title":"Ship it"}\n'
            '```'
        ),
        "raw": {"total_tokens": 11},
    }

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1},
    )

    assert [call.tool for call in turn.tool_calls] == ["add_issue_comment"]
    assert "tool-call recovery was partial" in turn.tool_calls[0].args["comment"]
    diagnostics = captured[0]["content"]
    assert '"recovery_complete": false' in diagnostics
    parsed = captured[1]["content"]
    assert "add_issue_comment" in parsed
    assert "write_file" not in parsed


def test_response_parser_unwraps_legacy_args_wrapper_inside_native_tool_calls(tmp_path: Path) -> None:
    """Layer: contract. Verifies native tool calls still accept the legacy nested args wrapper."""
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = SimpleNamespace(
        content="",
        raw={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"args":{"path":"agent_output/main.py","content":"x"}}',
                    },
                }
            ]
        },
    )

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1},
    )

    assert turn.tool_calls[0].args == {"path": "agent_output/main.py", "content": "x"}


def test_response_parser_filters_undeclared_native_tool_calls_and_dedupes_duplicates(tmp_path: Path) -> None:
    """Layer: contract. Verifies parser filtering drops undeclared native calls and exact duplicates."""
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = SimpleNamespace(
        content="",
        raw={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"args":{"path":"agent_output/requirements.txt"}}',
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "update_issue_status",
                        "arguments": '{"args":{"status":"done"}}',
                    },
                },
                {
                    "id": "call_3",
                    "type": "function",
                    "function": {
                        "name": "add_issue_comment",
                        "arguments": '{"args":{"comment":"extra"}}',
                    },
                },
                {
                    "id": "call_4",
                    "type": "function",
                    "function": {
                        "name": "update_issue_status",
                        "arguments": '{"args":{"status":"done"}}',
                    },
                },
            ]
        },
    )

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="integrity_guard",
        context={
            "session_id": "s1",
            "turn_index": 1,
            "verification_scope": {"declared_interfaces": ["read_file", "update_issue_status"]},
        },
    )

    assert [call.tool for call in turn.tool_calls] == ["read_file", "update_issue_status"]
    assert turn.tool_calls[0].args == {"path": "agent_output/requirements.txt"}
    assert turn.tool_calls[1].args == {"status": "done"}


def test_response_parser_prefers_declared_native_tool_names_when_provider_telemetry_is_present(tmp_path: Path) -> None:
    """Layer: contract. Verifies provider-recorded native tool telemetry overrides broader inferred interfaces."""
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = SimpleNamespace(
        content="",
        raw={
            "openai_native_tool_names": ["read_file"],
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"args":{"path":"agent_output/requirements.txt"}}',
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "update_issue_status",
                        "arguments": '{"args":{"status":"done"}}',
                    },
                },
            ],
        },
    )

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="integrity_guard",
        context={
            "session_id": "s1",
            "turn_index": 1,
            "verification_scope": {"declared_interfaces": ["read_file", "update_issue_status"]},
        },
    )

    assert [call.tool for call in turn.tool_calls] == ["read_file"]
    assert turn.tool_calls[0].args == {"path": "agent_output/requirements.txt"}


def test_response_parser_non_json_residue_and_guard_payload(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    residue = parser.non_json_residue('{"tool":"read_file","args":{"path":"x"}} trailing')
    payload = parser.extract_guard_review_payload(
        "```json\n"
        '{"rationale":"ok","violations":[],"remediation_actions":[]}\n'
        "```"
    )

    assert residue == "trailing"
    assert payload.get("rationale") == "ok"


def test_response_parser_non_json_residue_ignores_recovered_legacy_tool_only_payload(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    content = (
        '```json\n'
        '{\n'
        '  "tool": "write_file",\n'
        '  "args": {\n'
        '    "path": "agent_output/challenge_runtime/validator.py",\n'
        '    "content": "if task[\'duration\'] < 0:\\n'
        '    errors.append({\\n'
        '        \'message\': f\'Negative duration: {task["duration"]}\'\\n'
        '    })"\n'
        '  }\n'
        '}\n'
        '```\n\n'
        '```json\n'
        '{\n'
        '  "tool": "update_issue_status",\n'
        '  "args": {\n'
        '    "status": "code_review"\n'
        '  }\n'
        '}\n'
        '```'
    )

    residue = parser.non_json_residue(content)

    assert residue == ""


def test_response_parser_strict_protocol_mode_accepts_canonical_envelope(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"a.txt","content":"x"}}]}',
        "raw": {"total_tokens": 9},
    }
    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1, "protocol_governed_enabled": True},
    )
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].tool == "write_file"
    assert isinstance(turn.raw.get("proposal_hash"), str)
    assert len(turn.raw["proposal_hash"]) == 64
    assert isinstance(turn.raw.get("validator_version"), str)
    assert isinstance(turn.raw.get("protocol_hash"), str)
    assert isinstance(turn.raw.get("tool_schema_hash"), str)


def test_response_parser_strict_protocol_mode_rejects_duplicate_keys(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": '{"content":"","tool_calls":[{"tool":"write_file","args":{},"args":{}}]}',
        "raw": {"total_tokens": 9},
    }
    try:
        parser.parse_response(
            response=response,
            issue_id="ISSUE-1",
            role_name="coder",
            context={"session_id": "s1", "turn_index": 1, "protocol_governed_enabled": True},
        )
        raise AssertionError("expected ValueError for duplicate keys")
    except ValueError as exc:
        assert "E_DUPLICATE_KEY" in str(exc)


def test_response_parser_strict_protocol_mode_rejects_markdown_fences(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": '```json\n{"content":"","tool_calls":[{"tool":"write_file","args":{}}]}\n```',
        "raw": {"total_tokens": 9},
    }
    try:
        parser.parse_response(
            response=response,
            issue_id="ISSUE-1",
            role_name="coder",
            context={"session_id": "s1", "turn_index": 1, "protocol_governed_enabled": True},
        )
        raise AssertionError("expected ValueError for markdown fences")
    except ValueError as exc:
        assert "E_MARKDOWN_FENCE" in str(exc)


def test_response_parser_strict_protocol_mode_allows_markdown_fence_inside_string_arg(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": (
            '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"README.md","content":"```sh\\n'
            'python main.py\\n```"}}]}'
        ),
        "raw": {"total_tokens": 9},
    }

    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={"session_id": "s1", "turn_index": 1, "protocol_governed_enabled": True},
    )

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].args["content"] == "```sh\npython main.py\n```"


def test_response_parser_strict_protocol_mode_rejects_excess_tool_calls(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": (
            '{"content":"","tool_calls":['
            '{"tool":"write_file","args":{}},'
            '{"tool":"read_file","args":{}}]}'
        ),
        "raw": {"total_tokens": 9},
    }
    try:
        parser.parse_response(
            response=response,
            issue_id="ISSUE-1",
            role_name="coder",
            context={
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "max_tool_calls": 1,
            },
        )
        raise AssertionError("expected ValueError for too many tool calls")
    except ValueError as exc:
        assert "E_MAX_TOOL_CALLS" in str(exc)


def test_response_parser_strict_protocol_mode_uses_context_overrides_for_hash_metadata(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    response = {
        "content": '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"a.txt","content":"x"}}]}',
        "raw": {"total_tokens": 9},
    }
    turn = parser.parse_response(
        response=response,
        issue_id="ISSUE-1",
        role_name="coder",
        context={
            "session_id": "s1",
            "turn_index": 1,
            "protocol_governed_enabled": True,
            "validator_version": "turn-validator/custom",
            "protocol_hash": "p" * 64,
            "tool_schema_hash": "s" * 64,
        },
    )
    assert turn.raw["validator_version"] == "turn-validator/custom"
    assert turn.raw["protocol_hash"] == "p" * 64
    assert turn.raw["tool_schema_hash"] == "s" * 64


def test_response_parser_strips_leading_thinking_blocks_for_supported_formats(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **kwargs: None)  # type: ignore[no-untyped-def]
    content = (
        "<think>first pass</think>\n"
        "<think>second pass</think>\n"
        '{"tool":"write_file","args":{"path":"a.txt","content":"x"}}'
    )
    stripped, count = parser.strip_leading_thinking_blocks(content, "xml_think_tags")

    assert count == 2
    assert stripped.strip().startswith('{"tool":"write_file"')
