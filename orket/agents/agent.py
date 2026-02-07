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

    def __init__(self, name: str, description: str, tools: Dict[str, callable], provider: LocalModelProvider):
        self.name = name
        self.description = description
        self.tools = tools
        self.provider = provider
        self._prompt_patch: str | None = None
        
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
        family = "qwen" if "qwen" in model_name else "llama" if "llama" in model_name else "generic"
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

        prompt += f"\nSYNTAX DIALECT ({self.dialect.model_family}):\n"
        prompt += f"You MUST use this format for all file operations:\n{self.dialect.dsl_format}\n"
        
        prompt += "\nCONSTRAINTS:\n"
        for c in self.dialect.constraints:
            prompt += f"- {c}\n"
        
        prompt += f"\nGUARDRAIL: {self.dialect.hallucination_guard}\n"

        if self._prompt_patch:
            prompt += f"\n\nPATCH:\n{self._prompt_patch}"
            
        return prompt

    # ---------------------------------------------------------
    # Tool-call parsing
    # ---------------------------------------------------------
    def _parse_tool_call(self, text: str):
        """
        Aggressive Tool Extraction: Supports JSON and DSL.
        """
        text = text.strip()
        
        # 1. Look for JSON in markdown fences
        import re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and "tool" in data:
                    return data["tool"], data.get("args", {})
            except: pass

        # 2. Look for first { and last } (Loose JSON)
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                candidate = text[start:end+1]
                data = json.loads(candidate)
                if isinstance(data, dict) and "tool" in data:
                    return data["tool"], data.get("args", {})
        except: pass

        # 3. DSL Fallback: TOOL:, PATH:, CONTENT:
        if "TOOL:" in text and "PATH:" in text:
            lines = text.splitlines()
            tool, path, content_lines, in_content = None, None, [], False
            for line in lines:
                if line.startswith("TOOL:"): tool = line.replace("TOOL:", "").strip()
                elif line.startswith("PATH:"): path = line.replace("PATH:", "").strip()
                elif line.startswith("CONTENT:"):
                    in_content = True
                    rem = line.replace("CONTENT:", "").strip()
                    if rem: content_lines.append(rem)
                elif in_content: content_lines.append(line)
            
            if tool and path:
                content = "\n".join(content_lines)
                if content.startswith("```") and content.endswith("```"):
                    content = "\n".join(content.splitlines()[1:-1])
                return tool, {"path": path, "content": content}

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
        
        print(f"  [DEBUG] Raw response from {self.name}:\n{text}\n{'-'*40}")

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
        # This catches models that 'pretend' to call the function in text
        fn_matches = re.findall(r"write_file\(\s*path=[\"'](.*?)[\"']\s*,\s*content=[\"'](.*?)[\"']\s*\)", text, re.DOTALL)
        for path, content in fn_matches:
            # Unescape newlines if the model used \n
            content = content.replace("\\n", "\n").replace("\\\\", "\\")
            files.append({"path": path, "content": content})
        
        return files