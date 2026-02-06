from typing import Dict, Any
from orket.llm import LocalModelProvider
from orket.logging import log_event, log_model_usage
import json


class Agent:
    """
    Single authoritative Agent class for Orket.
    Handles:
    - Prompt construction
    - Model invocation
    - Tool-call parsing
    - Tool execution
    - Logging
    """

    def __init__(self, name: str, description: str, tools: Dict[str, callable], provider: LocalModelProvider):
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self._prompt_patch: str | None = None

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
        Expected format:
        {"tool": "write_file", "args": {"path": "...", "content": "..."}}
        """
        text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None, None

        if not isinstance(data, dict):
            return None, None

        tool = data.get("tool")
        args = data.get("args")

        if not isinstance(tool, str) or not isinstance(args, dict):
            return None, None

        return tool, args

    # ---------------------------------------------------------
    # Main agent execution
    # ---------------------------------------------------------
    def run(self, task: Dict[str, Any], context: Dict[str, Any], workspace):
        """
        Executes a single agent step:
        - Calls the model
        - Logs model usage (tokens)
        - Parses tool calls
        - Executes tools
        - Logs tool events
        - Returns a Response-like object
        """

        system_prompt = self._build_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task["description"]},
            {"role": "user", "content": f"Context: {context}"},
        ]

        result = self.provider.complete(messages)
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
            result = tool_fn(**args)

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
                },
                workspace=workspace,
            )

            return type(
                "Response",
                (),
                {
                    "content": f"Tool '{tool_name}' executed successfully.",
                    "note": f"role={self.name}, tool={tool_name}",
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
            )

            return type(
                "Response",
                (),
                {
                    "content": f"Tool '{tool_name}' failed with error: {e}",
                    "note": f"role={self.name}, tool={tool_name}, error",
                },
            )
