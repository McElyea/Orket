"""Layer: integration. Public response admission with real parser artifacts."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest

from orket.application.workflows.turn_response_capture import capture_turn_response
from orket.application.workflows.turn_response_parser import ResponseParser
from tests.integration.test_turn_parser_publication_ownership import _destination, _paths

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_NOW = datetime(2026, 10, 1, tzinfo=UTC)
_CALL = {"tool": "read_file", "args": {"path": "input.txt"}}


async def _parse(destination, response, **policy):
    return await ResponseParser(utc_now=lambda: _NOW).parse_response(
        response=capture_turn_response(response), destination=destination, context=policy,
    )


async def _artifacts(destination):
    return [json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
            for path in _paths(destination)]


@pytest.mark.parametrize("item,reason", [
    (None, "non_object"),
    ({"function": []}, "missing_function"),
    ({"function": {"name": "  ", "arguments": {}}}, "missing_name"),
    ({"function": {"name": "read_file", "arguments": "{"}}, "invalid_arguments_json"),
    ({"function": {"name": "read_file", "arguments": "[]"}}, "arguments_not_object"),
    ({"function": {"name": "read_file", "arguments": None}}, "arguments_not_object"),
    ({"function": {"name": "delete_file", "arguments": {}}}, "undeclared_tool"),
])
async def test_native_rejections_publish_reason_without_executable_call(tmp_path, item, reason):
    destination = _destination(tmp_path)
    turn = await _parse(destination, {"content": "", "tool_calls": [item]},
                        required_action_tools=["", "read_file", " "])
    diagnostics, calls, summary = await _artifacts(destination)
    assert not turn.tool_calls and calls == []
    assert summary == {"extraction_strategy": "none"}
    assert {"stage": "native_tool_call_skipped", "data": dict(
        index=0, reason=reason, **({"tool": "delete_file"} if reason == "undeclared_tool" else {}),
    )} in diagnostics


async def test_native_arguments_normalize_and_deduplicate_in_retained_files(tmp_path):
    destination = _destination(tmp_path)
    accepted = {"name": "read_file", "arguments": {"args": {"path": "input.txt"}}}
    equivalent = {"name": "read_file", "arguments": '{"path":"input.txt"}'}
    turn = await _parse(destination, dict(
        content="", total_tokens=17, openai_native_tool_names=["", "read_file", " "],
        tool_calls=[{"function": accepted}, {"function": equivalent}],
    ), verification_scope={"declared_interfaces": ["delete_file"]})
    diagnostics, calls, summary = await _artifacts(destination)
    assert calls == [_CALL]
    assert [(call.tool, call.args) for call in turn.tool_calls] == [("read_file", _CALL["args"])]
    assert turn.timestamp == _NOW and turn.tokens_used == 17
    assert summary == {"extraction_strategy": "provider_native_tool_calls"}
    assert {"stage": "native_tool_call_skipped", "data": {
        "index": 1, "reason": "duplicate_tool_call", "tool": "read_file",
    }} in diagnostics


@pytest.mark.parametrize("content,code", [
    (None, "E_PARSE_JSON"),
    ("{", "E_PARSE_JSON"),
    ("[]", "E_SCHEMA_ENVELOPE"),
    ('{"content":""}', "E_SCHEMA_ENVELOPE"),
    ('{"content":null,"tool_calls":[]}', "E_SCHEMA_ENVELOPE"),
    ('{"content":"","tool_calls":{}}', "E_SCHEMA_ENVELOPE"),
    ('{"content":"text","tool_calls":[]}', "E_TOOL_MODE_CONTENT_NON_EMPTY"),
    ('{"content":"","tool_calls":[]}', "E_MISSING_TOOL_CALLS"),
    ('{"content":"","tool_calls":[null]}', "E_SCHEMA_TOOL_CALL:0"),
    ('{"content":"","tool_calls":[{"tool":"read_file"}]}', "E_SCHEMA_TOOL_CALL:0"),
    ('{"content":"","tool_calls":[{"tool":" ","args":{}}]}', "E_SCHEMA_TOOL_CALL:0"),
    ('{"content":"","tool_calls":[{"tool":1,"args":{}}]}', "E_SCHEMA_TOOL_CALL:0"),
    ('{"content":"","tool_calls":[{"tool":"read_file","args":[]}]}', "E_SCHEMA_TOOL_CALL:0"),
    ('\u00a0{"content":"","tool_calls":[]}', "E_NON_ASCII_WHITESPACE"),
    ('{"content":"","tool_calls":[]}\u00a0', "E_NON_ASCII_WHITESPACE"),
])
@pytest.mark.parametrize("retained", [False, True], ids=["new", "existing"])
async def test_strict_refusal_precedes_all_parser_artifact_writes(tmp_path, content, code, retained):
    destination = _destination(tmp_path)
    paths = _paths(destination)
    if retained:
        await asyncio.to_thread(destination.output_dir.mkdir, parents=True)
        for path in paths:
            await asyncio.to_thread(path.write_bytes, b"retained prior observation\n")
    with pytest.raises(ValueError, match=code):
        await _parse(destination, {"content": content}, protocol_governed_enabled=True)
    if retained:
        for path in paths:
            assert await asyncio.to_thread(path.read_bytes) == b"retained prior observation\n"
    else:
        assert not await asyncio.to_thread(destination.output_dir.exists)


async def test_strict_utf8_byte_limit_counts_complete_envelope_and_retains_escape_content(tmp_path):
    destination = _destination(tmp_path)
    text = '"quoted" \\ path ```json \u00e9'
    call = {"tool": "write_file", "args": {"path": "output.txt", "content": text}}
    envelope = " \t\r\n" + json.dumps({"content": "", "tool_calls": [call]}, ensure_ascii=False) + "\n\t "
    byte_count = len(envelope.encode("utf-8"))
    with pytest.raises(ValueError, match="E_RESPONSE_BYTES"):
        await _parse(destination, {"content": envelope}, protocol_governed_enabled=True,
                     max_response_bytes=byte_count - 1)
    assert not await asyncio.to_thread(destination.output_dir.exists)
    turn = await _parse(destination, {"content": envelope}, protocol_governed_enabled=True,
                        max_response_bytes=byte_count, max_tool_calls=1)
    diagnostics, calls, summary = await _artifacts(destination)
    assert calls == [call] and turn.tool_calls[0].args["content"] == text
    assert diagnostics == [{"stage": "strict_parse_success", "data": {"tool_call_count": 1}}]
    assert summary == {"extraction_strategy": "strict_envelope"}
    assert turn.content == "" and len(turn.raw["proposal_hash"]) == 64
