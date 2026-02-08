from typing import Dict, Any, List
from pathlib import Path
from orket.llm import LocalModelProvider
from orket.logging import log_event, log_model_usage
import json


from orket.utils import sanitize_name

from orket.schema import SkillConfig, DialectConfig

class Agent:
    """
    Authority Agent class.
    Uses the 'Prompt Engine' to compile Skills + Dialects.
    """

    def __init__(self, name: str, description: str, tools: Dict[str, callable], provider: LocalModelProvider, next_member: str = None, prompt_patch: str = None):
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self.next_member = next_member
        self._prompt_patch = prompt_patch
        
        # New iDesign Prompt Engine Components
        self.skill: SkillConfig | None = None
        self.dialect: DialectConfig | None = None
        
        self._load_engine_configs()

    def _load_engine_configs(self):
        """
        iDesign: Decompose by Volatility.
        Loads the 'Skill' (Manager Intent) and 'Dialect' (Utility Syntax).
        """
        from orket.orket import ConfigLoader
        loader = ConfigLoader(Path("model"), "core")
        
        # 1. Load Skill based on Seat Name
        try:
            self.skill = loader.load_asset("skills", sanitize_name(self.name), SkillConfig)
        except:
            # Fallback to a generic skill if specific one missing
            pass

        # 2. Load Dialect based on Model Family
        model_name = self.provider.model.lower()
        if "deepseek" in model_name:
            family = "deepseek-r1"
        elif "llama" in model_name:
            family = "llama3"
        elif "phi" in model_name:
            family = "phi"
        elif "qwen" in model_name:
            family = "qwen"
        else:
            family = "generic"
            
        try:
            self.dialect = loader.load_asset("dialects", family, DialectConfig)
        except:
            pass

    def _build_system_prompt(self) -> str:
        """
        The Compiler: Skill + Dialect + iDesign Policies.
        """
        if not self.skill or not self.dialect:
            # Legacy fallback if configs aren't ready
            base = self.description
            base += "\n\nCRITICAL: You are an execution engine, not a chat bot."
            return base

        prompt = f"IDENTITY: {self.skill.name}\n"
        prompt += f"INTENT: {self.skill.intent}\n\n"
        
        prompt += "RESPONSIBILITIES:\n"
        for r in self.skill.responsibilities:
            prompt += f"- {r}\n"

        prompt += "\niDESIGN CONSTRAINTS (Structural Integrity):\n"
        # Standard iDesign structure injected for all technical roles
        idesign_standard = [
            "Maintain strict separation of concerns: Managers, Engines, Accessors, Utilities.",
            "Managers orchestrate the workflow and high-level logic.",
            "Engines handle complex computations or business rules.",
            "Accessors manage state or external tool interactions.",
            "Utilities provide cross-cutting logic.",
            "Organize files into: /controllers, /managers, /engines, /accessors, /utils, /tests."
        ]
        for c in (idesign_standard + self.skill.idesign_constraints):
            prompt += f"- {c}\n"

        prompt += "\nCARD SYSTEM PROTOCOL:\n"
        # Force models to use the new Card System tools
        prompt += "- ALWAYS start by calling 'get_issue_context' to read the comment history and intent.\n"
        prompt += "- Use 'add_issue_comment' to log your progress, reasoning, and final handoff memo.\n"
        prompt += "- The Card System is the Source of Truth for INTENT. Files are the result of EXECUTION.\n"

        prompt += f"\nSYNTAX DIALECT ({self.dialect.model_family}):\n"
        prompt += f"You MUST use this format for all file operations:\n{self.dialect.dsl_format}\n"
        
        prompt += "\nCONSTRAINTS:\n"
        for c in self.dialect.constraints:
            prompt += f"- {c}\n"
        
        prompt += f"\nGUARDRAIL: {self.dialect.hallucination_guard}\n"

        if self.next_member:
            prompt += f"\nWARM HANDOFF PROTOCOL:\n"
            prompt += f"Your work will be handed off to the '{self.next_member}'.\n"
            prompt += f"You MUST include a 'Member-to-Member Memo' in an 'add_issue_comment' call.\n"
            prompt += f"Tailor the language: if they are technical, be precise. If they are business/creative, focus on features and value.\n"

        if self._prompt_patch:
            prompt += f"\n\nPATCH:\n{self._prompt_patch}"
            
        return prompt

    # ---------------------------------------------------------
    # Tool-call parsing
    # ---------------------------------------------------------
    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Aggressive Multi-Tool Extraction: Uses stack-based JSON parsing,
        OpenAI-style translation, and multi-block DSL scanner.
        Supports both 'tool/args' and 'name/arguments' formats.
        """
        text = text.strip()
        results = []
        
        # 1. Look for JSON in markdown fences (Highest priority)
        import re
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    # Orket format
                    if "tool" in data:
                        results.append({"tool": data["tool"], "args": data.get("args", {})})
                    # Alternate 'name/arguments' format
                    elif "name" in data and "arguments" in data:
                        results.append({"tool": data["name"], "args": data["arguments"]})
            except: pass

        if results: return results

        # 2. Stack-based extraction for loose JSON
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
                            # Orket format
                            if isinstance(data, dict) and "tool" in data:
                                results.append({"tool": data["tool"], "args": data.get("args", {})})
                            # OpenAI name/arguments format
                            elif isinstance(data, dict) and "name" in data and "arguments" in data:
                                results.append({"tool": data["name"], "args": data["arguments"]})
                            # OpenAI single function format
                            elif isinstance(data, dict) and "function" in data:
                                f = data.get("function", {})
                                args = f.get("arguments", {})
                                if isinstance(args, str): 
                                    try: args = json.loads(args)
                                    except: pass
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
                            # OpenAI list format
                            if isinstance(data, list) and len(data) > 0 and "function" in data[0]:
                                for call in data:
                                    f = call.get("function", {})
                                    args = f.get("arguments", {})
                                    if isinstance(args, str):
                                        try: args = json.loads(args)
                                        except: pass
                                    results.append({"tool": f.get("name"), "args": args})
                        except: pass

        if results: return results

        # 3. Multi-block DSL Scanner: [TOOL] path: content:
        dsl_blocks = re.split(r"(?:\[|TOOL:\s*)(write_file|create_issue|add_issue_comment|get_issue_context)(?:\]|\s*)", text)
        if len(dsl_blocks) > 1:
            for i in range(1, len(dsl_blocks), 2):
                tool_name = dsl_blocks[i]
                block_content = dsl_blocks[i+1]
                path_match = re.search(r"(?:path|PATH):\s*([^\n]+)", block_content)
                content_match = re.search(r"(?:content|CONTENT):\s*\"*\"*\"*\n?(.*?)(?:\n\"*\"*\"*|$)", block_content, re.DOTALL)
                if path_match and content_match:
                    results.append({
                        "tool": tool_name,
                        "args": {"path": path_match.group(1).strip().strip("'").strip('"'), "content": content_match.group(1).strip()}
                    })
        
        return results

    # ---------------------------------------------------------
    # Main agent execution
    # ---------------------------------------------------------
    async def run(self, task: Dict[str, Any], context: Dict[str, Any], workspace, transcript: List[Dict[str, Any]] = None):
        """
        Executes a single agent step with transcript context.
        """
        import asyncio
        import re

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

        try:
            result = await self.provider.complete(messages)
            text = result.content if hasattr(result, "content") else str(result)
            
            # --- CHAIN OF THOUGHT EXTRACTION ---
            thought_match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
            if thought_match:
                thought_content = thought_match.group(1).strip()
                log_event("reasoning", {"thought": thought_content, "role": self.name}, workspace, role=self.name)
                text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()

            print(f"  [DEBUG] Raw response from {self.name}:\n{text}\n{'-'*40}")

            # Usage logging
            usage = result.raw if hasattr(result, "raw") else {}
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

            # Parse ALL tool calls
            tool_calls = self._parse_tool_calls(text)

            # --- FORCEFUL PERSISTENCE ---
            if not tool_calls and "```" in text:
                extracted_files = self._auto_extract_files(text)
                if extracted_files:
                    for f in extracted_files:
                        tool_calls.append({"tool": "write_file", "args": f})

            if not tool_calls:
                return type("Response", (), {"content": text, "note": f"role={self.name}", "usage": usage})

            # --- EXECUTE ALL TOOL CALLS ---
            execution_results = []
            for call in tool_calls:
                tool_name = call["tool"]
                args = call["args"]
                
                if tool_name not in self.tools:
                    execution_results.append(f"Error: Unknown tool '{tool_name}'")
                    continue

                tool_fn = self.tools[tool_name]
                try:
                    import inspect
                    if inspect.iscoroutinefunction(tool_fn):
                        tool_res = await tool_fn(args, context=context)
                    else:
                        tool_res = tool_fn(args, context=context)
                    
                    execution_results.append(f"Tool '{tool_name}' result: {tool_res}")
                    log_event("tool_call", {"role": self.name, "tool": tool_name, "args": args, "result": tool_res}, workspace, role=self.name)
                except Exception as e:
                    execution_results.append(f"Tool '{tool_name}' failed: {e}")

            return type("Response", (), {
                "content": f"Executed {len(tool_calls)} tools.\n" + "\n".join(execution_results),
                "note": f"role={self.name}, tools={len(tool_calls)}",
                "usage": usage
            })

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_event("tool_error", {"role": self.name, "error": str(e)}, workspace=workspace, role=self.name)
            return type("Response", (), {"content": f"Agent execution failed: {e}", "note": "error", "usage": {}})

    def _auto_extract_files(self, text: str) -> List[Dict[str, str]]:
        """
        Aggressively scans text for markdown code blocks and filename hints.
        Also scans for pseudo-function calls like write_file(path=..., content=...).
        """
        import re
        files = []
        
        # 1. Standard Markdown Blocks
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
            
            if not filename:
                if "# " in content[:50]: filename = f"document_{i+1}.md"
                elif "{" in content[:10]: filename = f"data_{i+1}.json"
                elif "import " in content or "def " in content: filename = f"script_{i+1}.py"
                else: filename = f"artifact_{i+1}.txt"
            
            files.append({"path": filename, "content": content})

        # 2. Heuristic: Look for write_file(path="...", content="...") style
        fn_matches = re.findall(r"write_file\(\s*path=[\"'](.*?)[\"']\s*,\s*content=[\"'](.*?)[\"']\s*\)", text, re.DOTALL)
        for path, content in fn_matches:
            content = content.replace("\\n", "\n").replace("\\\\", "\\")
            files.append({"path": path, "content": content})
        
        return files
