from typing import Dict, Any, List
from pathlib import Path
from orket.llm import LocalModelProvider
from orket.logging import log_event, log_model_usage
import json


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
        
        prompt_path = Path("prompts") / self.name / f"{family}.txt"
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
                step_index=context.get("step_index", -1),
                flow=context.get("flow_name", "unknown"),
                workspace=workspace,
            )

        # Try to interpret as a tool call
        tool_name, args = self._parse_tool_call(text)

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
