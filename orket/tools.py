import json
from pathlib import Path
from orket.utils import log_event

# ------------------------------------------------------------
# Tool Implementations
# ------------------------------------------------------------


def read_file(args: dict) -> dict:
    """
    Read a file from the workspace.
    args: { "path": "relative/path/to/file" }
    """
    path = Path(args["path"])

    if not path.exists():
        return {"error": f"File not found: {path}"}

    content = path.read_text(encoding="utf-8")
    return {"content": content}


def write_file(args: dict) -> dict:
    """
    Write content to a file in the workspace.
    args: { "path": "relative/path/to/file", "content": "text" }
    """
    path = Path(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(args["content"], encoding="utf-8")

    return {"status": "ok", "path": str(path), "bytes_written": len(args["content"])}


def list_dir(args: dict) -> dict:
    """
    List files in a directory.
    args: { "path": "relative/path" }
    """
    path = Path(args["path"])

    if not path.exists():
        return {"error": f"Directory not found: {path}"}

    if not path.is_dir():
        return {"error": f"Not a directory: {path}"}

    items = [p.name for p in path.iterdir()]
    return {"items": items}


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


def run_tool(tool_name: str, args: dict) -> dict:
    """
    Execute a tool by name.
    """
    if tool_name not in TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    tool_fn = TOOLS[tool_name]

    log_event({"type": "tool_execute", "tool": tool_name, "args": args})

    try:
        result = tool_fn(args)
    except Exception as e:
        return {"error": f"Tool '{tool_name}' failed: {e}"}

    return result


# ------------------------------------------------------------
# Tool Call Parsing
# ------------------------------------------------------------


def parse_tool_calls(content: str) -> list:
    """
    Extract tool calls from agent output.

    Supports JSON tool calls like:
    {
        "tool": "write_file",
        "args": { "path": "foo.txt", "content": "hello" }
    }

    Returns a list of tool call dicts.
    """
    tool_calls = []

    # Try to find JSON blocks
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "tool" in data and "args" in data:
            tool_calls.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "tool" in item and "args" in item:
                    tool_calls.append(item)
    except Exception:
        # Not JSON — ignore
        pass

    return tool_calls
