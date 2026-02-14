import json
import re
from typing import List, Dict, Any, Callable, Optional

class ToolParser:
    """
    Service responsible for extracting structured tool calls from raw model text.
    Standardized on stack-based JSON extraction for maximum robustness.
    """
    
    @staticmethod
    def parse(
        text: str,
        diagnostics: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        text = text.strip()
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
            emit("parse_success", {"strategy": "stack_json", "count": len(results)})
            return results

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
        else:
            emit("parse_empty", {"reason": "no_parseable_tool_calls"})
        return results
