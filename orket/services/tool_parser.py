import json
import re
from typing import List, Dict, Any

class ToolParser:
    """
    Service responsible for extracting structured tool calls from raw model text.
    Supports multiple JSON objects, OpenAI-style calls, and DSL blocks.
    """
    
    @staticmethod
    def parse(text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        results = []
        
        # 1. Markdown Fences
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    if "tool" in data: results.append({"tool": data["tool"], "args": data.get("args", {})})
                    elif "name" in data and "arguments" in data: results.append({"tool": data["name"], "args": data["arguments"]})
            except: pass

        if results: return results

        # 2. Stack-based Loose JSON
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
                                if "tool" in data: results.append({"tool": data["tool"], "args": data.get("args", {})})
                                elif "name" in data and "arguments" in data: results.append({"tool": data["name"], "args": data["arguments"]})
                                elif "function" in data:
                                    f = data.get("function", {})
                                    args = f.get("arguments", {})
                                    if isinstance(args, str): args = json.loads(args)
                                    results.append({"tool": f.get("name"), "args": args})
                        except: pass
            elif char == '[':
                if not stack: start_idx = i
                stack.append('[')
            elif char == ']':
                if stack:
                    stack.pop()
                    if not stack:
                        candidate = text[start_idx:i+1]
                        try:
                            data = json.loads(candidate)
                            if isinstance(data, list) and len(data) > 0 and "function" in data[0]:
                                for call in data:
                                    f = call.get("function", {})
                                    args = f.get("arguments", {})
                                    if isinstance(args, str): args = json.loads(args)
                                    results.append({"tool": f.get("name"), "args": args})
                        except: pass

        if results: return results

        # 3. DSL Scanner
        dsl_blocks = re.split(r"(?:\[|TOOL:\s*)(write_file|create_issue|add_issue_comment|get_issue_context)(?:\]|\s*)", text)
        if len(dsl_blocks) > 1:
            for i in range(1, len(dsl_blocks), 2):
                tool_name = dsl_blocks[i]
                block_content = dsl_blocks[i+1]
                path_match = re.search(r"(?:path|PATH):\s*([^\n]+)", block_content)
                content_match = re.search(r"(?:content|CONTENT):\s*\"*\"*\"*\n?(.*?)(?:\n\"*\"*\"*|$)", block_content, re.DOTALL)
                if path_match and content_match:
                    results.append({"tool": tool_name, "args": {"path": path_match.group(1).strip().strip("'").strip('"'), "content": content_match.group(1).strip()}})
        
        return results