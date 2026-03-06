from __future__ import annotations

import hashlib
import json


def prompt_for_case(task_class: str, case_id: str) -> str:
    if task_class == "tool_call":
        return (
            "Return ONLY this JSON object with no prose or markdown: "
            f'{{"tool":"read_file","args":{{"path":"README.md","case_id":"{case_id}"}}}}'
        )
    return f'Return ONLY this JSON object with no prose or markdown: {{"ok":true,"case_id":"{case_id}"}}'


def validate_case(task_class: str, content: str, case_id: str) -> tuple[bool, str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return False, "JSON_PARSE_ERROR"
    if not isinstance(payload, dict):
        return False, "SCHEMA_MISMATCH"
    if task_class == "tool_call":
        tool = str(payload.get("tool") or "").strip()
        args = payload.get("args")
        if not tool or not isinstance(args, dict):
            return False, "TOOL_SHAPE_INVALID"
        return True, ""
    ok = payload.get("ok")
    parsed_case_id = str(payload.get("case_id") or "").strip()
    if ok is not True or parsed_case_id != case_id:
        return False, "SCHEMA_MISMATCH"
    return True, ""


def mock_content(task_class: str, case_id: str) -> str:
    if task_class == "tool_call":
        return json.dumps({"tool": "read_file", "args": {"path": "README.md", "case_id": case_id}})
    return json.dumps({"ok": True, "case_id": case_id})


def resolve_case_counts(*, suite: str, cases: int, strict_json_cases: int, tool_call_cases: int) -> tuple[int, int]:
    if suite == "promotion":
        strict_default, tool_default = 1000, 500
    else:
        strict_default = max(1, int(cases))
        tool_default = max(1, int(cases))
    strict_count = max(1, int(strict_json_cases)) if int(strict_json_cases) > 0 else strict_default
    tool_count = max(1, int(tool_call_cases)) if int(tool_call_cases) > 0 else tool_default
    return strict_count, tool_count


def anti_meta_flags(content: str) -> dict[str, bool]:
    markdown_fence = "```" in content
    trimmed = str(content or "").strip(" \t\r\n")
    if not trimmed:
        return {"markdown_fence": markdown_fence, "protocol_chatter": True}
    decoder = json.JSONDecoder()
    try:
        _, end_pos = decoder.raw_decode(trimmed)
        remainder = trimmed[end_pos:].strip(" \t\r\n")
        return {"markdown_fence": markdown_fence, "protocol_chatter": bool(remainder)}
    except json.JSONDecodeError:
        return {"markdown_fence": markdown_fence, "protocol_chatter": True}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
