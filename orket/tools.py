# orket/tools.py
import json
from pathlib import Path
from typing import Dict, Any, List

from orket.policy import load_policy


# ------------------------------------------------------------
# Lazy-loaded policy
# ------------------------------------------------------------

_POLICY = None

def _policy():
    global _POLICY
    if _POLICY is None:
        _POLICY = load_policy()
    return _POLICY


# ------------------------------------------------------------
# Tool Implementations
# ------------------------------------------------------------

def _resolve_path(path_str: str, workspace: str) -> Path:
    """
    Resolves a path string. If relative, joins with the current workspace.
    """
    path = Path(path_str)
    if not path.is_absolute():
        return (Path(workspace) / path).resolve()
    return path.resolve()


def read_file(args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    args: { "path": "relative/or/absolute/path" }
    """
    path_str = args.get("path")
    if not path_str:
        return {"ok": False, "error": "Missing 'path' argument"}
    
    workspace = context.get("workspace", ".") if context else "."
    path = _resolve_path(path_str, workspace)
    policy = _policy()

    if not policy.can_read(str(path)):
        return {"ok": False, "error": f"Read not allowed: {path}"}

    try:
        if not path.exists():
             return {"ok": False, "error": f"File not found: {path}"}
        content = path.read_text(encoding="utf-8")
        return {"ok": True, "content": content}
    except Exception as e:
        return {"ok": False, "error": f"Failed to read file: {e}"}


def write_file(args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    args: { "path": "relative/or/absolute/path", "content": "text" }
    """
    path_str = args.get("path")
    content = args.get("content", "")
    if not path_str:
        return {"ok": False, "error": "Missing 'path' argument"}

    workspace = context.get("workspace", ".") if context else "."
    path = _resolve_path(path_str, workspace)
    policy = _policy()

    if not policy.can_write(str(path)):
        return {"ok": False, "error": f"Write not allowed: {path}"}

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return {"ok": False, "error": f"Failed to write file: {e}"}


def list_dir(args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    args: { "path": "relative/or/absolute/path" }
    """
    path_str = args.get("path", ".")
    workspace = context.get("workspace", ".") if context else "."
    path = _resolve_path(path_str, workspace)
    policy = _policy()

    # Listing a directory is a read operation
    if not policy.can_read(str(path)):
        return {"ok": False, "error": f"Directory read not allowed: {path}"}

    if not path.exists():
        return {"ok": False, "error": f"Directory not found: {path}"}

    if not path.is_dir():
        return {"ok": False, "error": f"Not a directory: {path}"}

    try:
        items = [p.name for p in path.iterdir()]
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "error": f"Failed to list directory: {e}"}


# ------------------------------------------------------------
# Tool Registry
# ------------------------------------------------------------

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
}


# ------------------------------------------------------------
# Tool Execution
# ------------------------------------------------------------

def run_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by name.
    """
    if tool_name not in TOOLS:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    tool_fn = TOOLS[tool_name]

    try:
        return tool_fn(args)
    except Exception as e:
        return {"ok": False, "error": f"Tool '{tool_name}' failed: {e}"}


# ------------------------------------------------------------
# Tool Call Parsing
# ------------------------------------------------------------

def parse_tool_calls(content: str) -> List[Dict[str, Any]]:
    """
    Extract tool calls from agent output.

    Supports JSON tool calls like:
    {
        "tool": "write_file",
        "args": { "path": "foo.txt", "content": "hello" }
    }

    Returns a list of tool call dicts.
    """
    calls: List[Dict[str, Any]] = []

    try:
        data = json.loads(content)

        if isinstance(data, dict) and "tool" in data and "args" in data:
            calls.append(data)

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "tool" in item and "args" in item:
                    calls.append(item)

    except Exception:
        # Not JSON — ignore
        pass

    return calls
