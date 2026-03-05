import json
import re
from typing import List, Dict, Any, Callable, Optional

class ToolParser:
    """
    Service responsible for extracting structured tool calls from raw model text.
    Standardized on stack-based JSON extraction for maximum robustness.
    """

    @staticmethod
    def _decode_relaxed_string(value: str) -> str:
        raw = value or ""
        try:
            return json.loads(f"\"{raw}\"")
        except json.JSONDecodeError:
            return (
                raw.replace("\\\\", "\\")
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"')
            )

    @staticmethod
    def _dedupe_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for call in tool_calls:
            key = json.dumps(call, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(call)
        return deduped

    @staticmethod
    def _likely_truncated_json(text: str) -> bool:
        blob = text or ""
        return blob.count("{") > blob.count("}")

    @staticmethod
    def _recover_truncated_tool_calls(
        text: str,
        diagnostics: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        cleaned = re.sub(r"```(?:json)?", " ", text or "", flags=re.IGNORECASE).replace("```", " ")
        tool_markers = list(re.finditer(r'"tool"\s*:\s*"(?P<tool>[a-zA-Z0-9_]+)"', cleaned))
        if not tool_markers:
            return []

        recovered: List[Dict[str, Any]] = []
        for idx, marker in enumerate(tool_markers):
            tool_name = marker.group("tool")
            segment_start = marker.start()
            segment_end = tool_markers[idx + 1].start() if idx + 1 < len(tool_markers) else len(cleaned)
            segment = cleaned[segment_start:segment_end]

            if tool_name == "update_issue_status":
                status_match = re.search(r'"status"\s*:\s*"([^"]+)"', segment, flags=re.DOTALL)
                if status_match:
                    recovered.append({"tool": tool_name, "args": {"status": status_match.group(1)}})
                continue

            if tool_name != "write_file":
                continue

            path_match = re.search(r'"path"\s*:\s*"([^"]+)"', segment, flags=re.DOTALL)
            content_match = re.search(r'"content"\s*:\s*"', segment, flags=re.DOTALL)
            if not path_match or not content_match:
                continue

            content_start = content_match.end()
            trailing = segment[content_start:]
            # Truncated generations often omit the final closing quote/braces. Recover by
            # taking the remainder when no valid terminator is found.
            terminator = re.search(r'(?<!\\)"\s*(?:[},]|$)', trailing, flags=re.DOTALL)
            raw_content = trailing[: terminator.start()] if terminator else trailing
            raw_content = raw_content.strip().replace("```", "").rstrip()
            if not raw_content:
                continue

            recovered.append(
                {
                    "tool": tool_name,
                    "args": {
                        "path": path_match.group(1),
                        "content": ToolParser._decode_relaxed_string(raw_content),
                    },
                }
            )

        if recovered and diagnostics is not None:
            diagnostics(
                "parse_partial_recovery",
                {
                    "strategy": "truncated_json_recovery",
                    "count": len(recovered),
                    "tools": [item.get("tool") for item in recovered],
                },
            )
        return recovered
    
    @staticmethod
    def parse(
        text: str,
        diagnostics: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        text = ToolParser.normalize_json_stringify(text or "").strip()
        results = []

        def _coerce_args(value: Any) -> Dict[str, Any]:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    return {}
            return {}

        def _extract_tool_calls(payload: Any) -> List[Dict[str, Any]]:
            extracted: List[Dict[str, Any]] = []

            if isinstance(payload, list):
                for item in payload:
                    extracted.extend(_extract_tool_calls(item))
                return extracted

            if not isinstance(payload, dict):
                return extracted

            if "tool" in payload:
                tool_name = payload.get("tool")
                if isinstance(tool_name, str) and tool_name:
                    extracted.append({"tool": tool_name, "args": _coerce_args(payload.get("args", {}))})
                return extracted

            if "name" in payload and "arguments" in payload:
                tool_name = payload.get("name")
                if isinstance(tool_name, str) and tool_name:
                    extracted.append({"tool": tool_name, "args": _coerce_args(payload.get("arguments", {}))})
                return extracted

            if "function" in payload and isinstance(payload.get("function"), dict):
                function_payload = payload.get("function", {})
                tool_name = function_payload.get("name")
                if isinstance(tool_name, str) and tool_name:
                    extracted.append({"tool": tool_name, "args": _coerce_args(function_payload.get("arguments", {}))})
                return extracted

            for key in ("tool_calls", "calls"):
                nested = payload.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        extracted.extend(_extract_tool_calls(item))
                    return extracted

            return extracted

        def emit(stage: str, data: Dict[str, Any]) -> None:
            if diagnostics:
                diagnostics(stage, data)

        emit("parse_start", {"text_length": len(text)})
        
        # 1. Stack-based JSON extraction (Robust against nested blocks and conversational noise)
        stack = []
        start_idx = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if not stack: start_idx = i
                stack.append('{')
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack:
                        candidate = text[start_idx:i+1]
                        try:
                            data = json.loads(candidate)
                            parsed = _extract_tool_calls(data)
                            if parsed:
                                results.extend(parsed)
                            elif isinstance(data, dict):
                                emit(
                                    "json_candidate_ignored",
                                    {
                                        "reason": "missing_tool_keys",
                                        "keys": sorted(data.keys())[:12],
                                        "candidate_preview": candidate[:180],
                                    },
                                )
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            emit(
                                "json_candidate_rejected",
                                {
                                    "reason": type(e).__name__,
                                    "candidate_preview": candidate[:180],
                                },
                            )

        if results:
            recovered: List[Dict[str, Any]] = []
            if ToolParser._likely_truncated_json(text):
                recovered = ToolParser._recover_truncated_tool_calls(text, diagnostics=diagnostics)
            merged = ToolParser._dedupe_tool_calls([*results, *recovered]) if recovered else results
            strategy = "stack_json+truncated_json_recovery" if len(merged) > len(results) else "stack_json"
            emit("parse_success", {"strategy": strategy, "count": len(merged)})
            return merged

        # 2. Legacy DSL Fallback (Regex based - fragile)
        dsl_blocks = re.split(r"(?:\[|TOOL:\s*)(write_file|create_issue|add_issue_comment|get_issue_context)(?:\]|\s*)", text)
        if len(dsl_blocks) > 1:
            for i in range(1, len(dsl_blocks), 2):
                tool_name = dsl_blocks[i]
                block_content = dsl_blocks[i+1]
                path_match = re.search(r"(?:path|PATH):\s*([^\n]+)", block_content)
                content_match = re.search(r"(?:content|CONTENT):\s*\"*\"*\"*\n?(.*?)(?:\n\"*\"*\"*|$)", block_content, re.DOTALL)
                if path_match and content_match:
                    results.append({"tool": tool_name, "args": {"path": path_match.group(1).strip().strip("'").strip('"'), "content": content_match.group(1).strip()}})
                else:
                    emit(
                        "dsl_block_rejected",
                        {"tool": tool_name, "has_path": bool(path_match), "has_content": bool(content_match)},
                    )

        if results:
            emit("parse_success", {"strategy": "legacy_dsl", "count": len(results)})
            return results

        recovered = ToolParser._recover_truncated_tool_calls(text, diagnostics=diagnostics)
        if recovered:
            emit("parse_success", {"strategy": "truncated_json_recovery", "count": len(recovered)})
            return recovered
        else:
            emit("parse_empty", {"reason": "no_parseable_tool_calls"})
        return []

    @staticmethod
    def normalize_json_stringify(text: str) -> str:
        """
        Convert JavaScript-style JSON.stringify(payload) expressions into JSON strings.
        This keeps tool-call extraction deterministic when models emit JS-flavored wrappers.
        """
        blob = text or ""
        marker = "JSON.stringify("
        if marker not in blob:
            return blob

        out: List[str] = []
        idx = 0
        while idx < len(blob):
            marker_idx = blob.find(marker, idx)
            if marker_idx == -1:
                out.append(blob[idx:])
                break

            out.append(blob[idx:marker_idx])
            expr_start = marker_idx + len(marker)

            depth = 1
            pos = expr_start
            in_string = False
            escaped = False
            while pos < len(blob):
                ch = blob[pos]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            break
                pos += 1

            if depth != 0:
                out.append(blob[marker_idx:])
                break

            inner = blob[expr_start:pos].strip()
            try:
                parsed_inner = json.loads(inner)
                normalized_inner = json.dumps(parsed_inner, ensure_ascii=False, separators=(",", ":"))
            except json.JSONDecodeError:
                normalized_inner = inner

            out.append(json.dumps(normalized_inner, ensure_ascii=False))
            idx = pos + 1

        return "".join(out)
