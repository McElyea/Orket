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
                            if isinstance(data, dict):
                                # Normalize different LLM output formats
                                if "tool" in data: 
                                    results.append({"tool": data["tool"], "args": data.get("args", {})})
                                elif "name" in data and "arguments" in data: 
                                    # OpenAI style
                                    args = data["arguments"]
                                    if isinstance(args, str): args = json.loads(args)
                                    results.append({"tool": data["name"], "args": args})
                                elif "function" in data:
                                    f = data.get("function", {})
                                    args = f.get("arguments", {})
                                    if isinstance(args, str): args = json.loads(args)
                                    results.append({"tool": f.get("name"), "args": args})
                                else:
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
