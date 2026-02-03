# Orket Examples

This document provides simple, self‑contained examples showing how Orket is configured and extended.  
It includes:

1. Example config.json  
2. Example agent definition  
3. Example tool definition  

These examples are intentionally minimal and aligned with the current Orket architecture.

---

## 1. Example config.json

{
  "workspace_dir": "C:\\Source",
  "task_memory_dir": "task_memory",
  "max_rounds": 5,
  "enable_path_translation": true,
  "models": {
    "architect": "deepseek-r1:32b",
    "coder": "qwen3-coder:latest",
    "reviewer": "llama3.1:8b"
  },
  "permissions": {
    "workspace_required_for_writes": true,
    "reference_space_read_only": true,
    "allow_writes_in_work_domain_if_no_workspace": true
  }
}

---

## 2. Example Agent Definition

This is a simplified example showing how an agent object may be structured inside Orket.

class Agent:
    def __init__(self, name, role, model, system_prompt, tools):
        self.name = name
        self.role = role
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools

    def generate(self, message):
        return ollama.generate(
            model=self.model,
            prompt=self.system_prompt + "\n" + message
        )

---

## 3. Example Tool Definition

This example shows a minimal tool with safety wrapping and registration.

from tools import tool

@tool(name="python_exec", description="Execute Python code in a sandboxed environment.")
def python_exec(code: str) -> str:
    import subprocess, tempfile, os

    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
        tmp.write(code.encode("utf-8"))
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout + result.stderr
    finally:
        os.remove(tmp_path)

    return output
