from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re
import asyncio
import inspect

from orket.llm import LocalModelProvider
from orket.logging import log_event, log_model_usage
from orket.utils import sanitize_name
from orket.schema import SkillConfig, DialectConfig
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.services.prompt_compiler import PromptCompiler
from orket.services.tool_parser import ToolParser

class Agent:
    """
    Application Service: Orchestrates the execution of a single agent turn.
    Delegates to specialized services for prompt compilation and tool parsing.
    """

    def __init__(self, name: str, description: str, tools: Dict[str, callable], provider: LocalModelProvider, next_member: str = None, prompt_patch: str = None, config_root: Optional[Path] = None, tool_gate=None):
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self.next_member = next_member
        self._prompt_patch = prompt_patch
        self.config_root = config_root or Path(".").resolve()
        self.tool_gate = tool_gate  # Optional ToolGate for mechanical enforcement

        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        self._load_configs()

    def _load_configs(self):
        from orket.orket import ConfigLoader
        loader = ConfigLoader(self.config_root, "core")
        try: self.skill = loader.load_asset("roles", sanitize_name(self.name), SkillConfig)
        except: pass

        model_name = self.provider.model.lower()
        family = "generic"
        if "deepseek" in model_name: family = "deepseek-r1"
        elif "llama" in model_name: family = "llama3"
        elif "phi" in model_name: family = "phi"
        elif "qwen" in model_name: family = "qwen"
            
        try: self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except: pass

    def get_compiled_prompt(self) -> str:
        """Returns the fully compiled system instructions for this agent."""
        if self.skill and self.dialect:
            return PromptCompiler.compile(self.skill, self.dialect, self.next_member, self._prompt_patch)
        return self.description

    async def run(self, task: Dict[str, Any], context: Dict[str, Any], workspace: Path, transcript: List[Dict] = None) -> ExecutionTurn:
        """Executes the turn and returns a structured ExecutionTurn object."""
        
        # 1. COMPILE INSTRUCTIONS
        system_prompt = PromptCompiler.compile(self.skill, self.dialect, self.next_member, self._prompt_patch) if self.skill and self.dialect else self.description

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task['description']}"},
        ]

        if transcript:
            history = "Previous steps:\n" + "\n".join([f"[{t['role']}] {t['summary']}" for t in transcript])
            messages.append({"role": "user", "content": history})

        messages.append({"role": "user", "content": f"Context: {context}"})

        # 2. GENERATE RESPONSE
        result = await self.provider.complete(messages)
        text = result.content if hasattr(result, "content") else str(result)
        
        # Extract Thought
        thought = None
        thought_match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()

        # 3. PARSE & EXECUTE TOOLS
        parsed_calls = ToolParser.parse(text)
        turn = ExecutionTurn(
            role=self.name, 
            issue_id=context.get("issue_id", "unknown"),
            thought=thought,
            content=text,
            tokens_used=getattr(result, "raw", {}).get("total_tokens", 0),
            raw=getattr(result, "raw", {})
        )

        for call in parsed_calls:
            tool_name = call["tool"]
            args = call["args"]

            if tool_name not in self.tools:
                turn.tool_calls.append(ToolCall(tool=tool_name, args=args, error=f"Unknown tool '{tool_name}'"))
                continue

            # --- TOOL GATE: Pre-execution validation ---
            if self.tool_gate:
                roles = context.get("roles", [self.name])
                gate_error = self.tool_gate.validate(tool_name, args, context, roles)
                if gate_error:
                    turn.tool_calls.append(ToolCall(tool=tool_name, args=args, error=f"[GATE] {gate_error}"))
                    log_event("tool_blocked", {"tool": tool_name, "args": args, "reason": gate_error}, workspace, role=self.name)
                    continue

            # --- TOOL EXECUTION ---
            tool_fn = self.tools[tool_name]
            try:
                res = await tool_fn(args, context=context) if inspect.iscoroutinefunction(tool_fn) else tool_fn(args, context=context)
                turn.tool_calls.append(ToolCall(tool=tool_name, args=args, result=res))
                log_event("tool_call", {"tool": tool_name, "args": args, "result": res}, workspace, role=self.name)
            except Exception as e:
                turn.tool_calls.append(ToolCall(tool=tool_name, args=args, error=str(e)))

        turn.note = f"role={self.name}, tools={len(turn.tool_calls)}"
        return turn