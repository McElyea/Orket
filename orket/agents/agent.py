from typing import Dict, Any, List
from pathlib import Path
from orket.llm import LocalModelProvider
from orket.logging import log_event, log_model_usage
import json


from orket.utils import sanitize_name

class Agent:
    """
    Single authoritative Agent class for Orket.
    """

    def __init__(self, name: str, description: str, tools: Dict[str, callable], provider: LocalModelProvider):
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self._prompt_patch: str | None = None
        
        # Load model-specific instructions if they exist
        self._load_model_specific_prompt()

    def _load_model_specific_prompt(self):
        """
        Looks for model-specific overrides in prompts/{role}/{model_family}.txt
        e.g., prompts/coder/qwen.txt
        """
        model_name = self.provider.model.lower()
        family = "unknown"
        if "qwen" in model_name: family = "qwen"
        elif "llama" in model_name: family = "llama"
        elif "deepseek" in model_name: family = "deepseek"
        elif "gemma" in model_name: family = "gemma"
        
        # Sanitize seat name for directory lookup
        safe_name = sanitize_name(self.name)
        prompt_path = Path("prompts") / safe_name / f"{family}.txt"
        if prompt_path.exists():
            try:
                override = prompt_path.read_text(encoding="utf-8")
                self.description = override
            except Exception:
                pass

    # ---------------------------------------------------------
    # Prompt patching
    # ---------------------------------------------------------
    def apply_prompt_patch(self, patch: str | None) -> None:
        self._prompt_patch = patch

    def _build_system_prompt(self) -> str:
        base = self.description
        if self._prompt_patch:
            base += "\n\n" + self._prompt_patch
        return base

    # ---------------------------------------------------------
    # Tool-call parsing
    # ---------------------------------------------------------
    def _parse_tool_call(self, text: str):
        """
        Supports both JSON and the DSL:
        TOOL: write_file
        PATH: ...
        CONTENT: ...
        """
        text = text.strip()
        
        # Try DSL first
        if "TOOL:" in text and "PATH:" in text:
            lines = text.splitlines()
            tool = None
            path = None
            content_lines = []
            in_content = False

            for line in lines:
                if line.startswith("TOOL:"):
                    tool = line.replace("TOOL:", "").strip()
                elif line.startswith("PATH:"):
                    path = line.replace("PATH:", "").strip()
                elif line.startswith("CONTENT:"):
                    in_content = True
                    # If there's content on the same line after CONTENT:
                    remainder = line.replace("CONTENT:", "").strip()
                    if remainder:
                        content_lines.append(remainder)
                elif in_content:
                    content_lines.append(line)
            
            if tool and path:
                content = "\n".join(content_lines)
                # Auto-strip markdown fences if present
                if content.startswith("```") and content.endswith("```"):
                    content = "\n".join(content.splitlines()[1:-1])
                return tool, {"path": path, "content": content}

        # Fallback to JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "tool" in data:
                return data["tool"], data.get("args", {})
        except json.JSONDecodeError:
            pass

        return None, None

    # ---------------------------------------------------------
    # Main agent execution
    # ---------------------------------------------------------
    async def run(self, task: Dict[str, Any], context: Dict[str, Any], workspace, transcript: List[Dict[str, Any]] = None):
        """
        Executes a single agent step with transcript context.
        """

        system_prompt = self._build_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task['description']}"},
        ]

        # Inject transcript for context
        if transcript:
            history = "Previous steps in this session:\n"
            for entry in transcript:
                history += f"\n[Step {entry['step_index']} - {entry['role']}]\n"
                if entry.get("note"):
                    history += f"Note: {entry['note']}\n"
                history += f"{entry['summary']}\n"
            messages.append({"role": "user", "content": history})

        messages.append({"role": "user", "content": f"Context: {context}"})

        result = await self.provider.complete(messages)
        text = result.content if hasattr(result, "content") else str(result)

        # Agent-level model usage logging (raw token counts)
        if hasattr(result, "raw"):
            tokens = {
                "input_tokens": result.raw.get("input_tokens"),
                "output_tokens": result.raw.get("output_tokens"),
                "total_tokens": result.raw.get("total_tokens"),
            }
            log_model_usage(
                role=self.name,
                model=result.raw.get("model", getattr(self.provider, "model", "unknown")),
                tokens=tokens,
                step_index=context.get("story_index", -1),
                epic=context.get("epic_name", "unknown"),
                workspace=workspace,
            )

        # Try to interpret as a tool call
        tool_name, args = self._parse_tool_call(text)

        # --- FORCEFUL PERSISTENCE (Auto-Extract) ---
        if tool_name is None and "```" in text:
            extracted_files = self._auto_extract_files(text)
            tool_fn = self.tools.get("write_file")
            
            if extracted_files and tool_fn:
                persist_notes = []
                for file_info in extracted_files:
                    path_str, content = file_info["path"], file_info["content"]
                    try:
                        import inspect
                        if inspect.iscoroutine(tool_fn) or inspect.iscoroutinefunction(tool_fn):
                            res = await tool_fn({"path": path_str, "content": content}, context=context)
                        else:
                            res = tool_fn({"path": path_str, "content": content}, context=context)
                        
                        if res.get("ok"):
                            persist_notes.append(path_str)
                            log_event("auto_persist", {"path": path_str, "role": self.name}, workspace=workspace)
                        else:
                            pass
                    except: pass
                
                if persist_notes:
                    return type("Response", (), {
                        "content": f"[AUTO-PERSISTED: {', '.join(persist_notes)}]\n\n{text}",
                        "note": f"role={self.name}, auto_persist"
                    })

        if tool_name is None:
            # No tool call — return raw text
            return type("Response", (), {"content": text, "note": f"role={self.name}"})

        # Validate tool
        if tool_name not in self.tools:
            msg = f"Unknown tool '{tool_name}'. Available tools: {list(self.tools.keys())}"
            return type("Response", (), {"content": msg, "note": f"role={self.name}"})

        tool_fn = self.tools[tool_name]

        # Execute tool
        try:
            import asyncio
            # Handle both sync and async tool functions
            if asyncio.iscoroutinefunction(tool_fn):
                tool_result = await tool_fn(args, context=context)
            else:
                tool_result = tool_fn(args, context=context)

            # Compute byte size for logging
            content_bytes = 0
            if isinstance(args.get("content"), str):
                content_bytes = len(args["content"].encode("utf-8"))

            log_event(
                "tool_call",
                {
                    "role": self.name,
                    "tool": tool_name,
                    "args": args,
                    "content_bytes": content_bytes,
                    "result": tool_result
                },
                workspace=workspace,
                role=self.name,
            )

            if tool_result.get("ok"):
                return type(
                    "Response",
                    (),
                    {
                        "content": f"Tool '{tool_name}' executed successfully. Result: {tool_result}",
                        "note": f"role={self.name}, tool={tool_name}",
                    },
                )
            else:
                return type(
                    "Response",
                    (),
                    {
                        "content": f"Tool '{tool_name}' failed: {tool_result.get('error')}",
                        "note": f"role={self.name}, tool={tool_name}, error",
                    },
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_event(
                "tool_error",
                {
                    "role": self.name,
                    "tool": tool_name,
                    "args": args,
                    "error": str(e),
                },
                workspace=workspace,
                role=self.name,
            )

            return type(
                "Response",
                (),
                {
                    "content": f"Tool '{tool_name}' failed with error: {e}",
                    "note": f"role={self.name}, tool={tool_name}, error",
                },
            )

    def _auto_extract_files(self, text: str) -> List[Dict[str, str]]:
        """
        Aggressively scans text for markdown code blocks and filename hints.
        """
        import re
        files = []
        # Support various code block styles
        blocks = re.findall(r"```(?:\w+)?\s*\n(.*?)\n```", text, re.DOTALL)
        segments = re.split(r"```(?:\w+)?\s*\n.*?\n```", text, flags=re.DOTALL)
        
        for i, block in enumerate(blocks):
            if i >= len(segments): break
            content = block.strip()
            if len(content) < 5: continue

            # Try to find a hint in the last few lines before the block
            pre_context = segments[i].strip().splitlines()[-3:]
            pre_text = " ".join(pre_context)
            
            filename = None
            patterns = [
                r"(?:[Ff]ile|[Pp]ath|写入|[Cc]reate|新建|Name|Target):\s*([\w\.\-/]+\.\w+)",
                r"\*\*([\w\.\-/]+\.\w+)\*\*",
                r"([\w\.\-/]+\.\w+):",
                r"(?:^|\s)([\w\.\-/]+\.\w+)(?:\s|$)"
            ]
            
            for p in patterns:
                match = re.search(p, pre_text)
                if match:
                    filename = match.group(1)
                    break
            
            # Fallback for common types
            if not filename:
                if "# " in content[:50]: filename = f"document_{i+1}.md"
                elif "{" in content[:10]: filename = f"data_{i+1}.json"
                elif "import " in content or "def " in content: filename = f"script_{i+1}.py"
                else: filename = f"artifact_{i+1}.txt"
            
            files.append({"path": filename, "content": content})
        
        return files