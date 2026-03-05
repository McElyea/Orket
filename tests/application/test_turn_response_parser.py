from __future__ import annotations

from pathlib import Path

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
