# dispatcher.py
import os
from datetime import datetime

from orket.utils import log_event
from orket.tools import run_tool
from orket.filesystem import FilesystemPolicy


class ToolDispatcher:
    def __init__(self, fs_policy: FilesystemPolicy):
        self.fs = fs_policy

    def execute(self, tool_name: str, args: dict) -> dict:
        """
        Enforce filesystem policy, execute the tool, and emit receipts.
        """
        path = args.get("path")

        if path:
            abs_path = os.path.abspath(path)

            if tool_name == "read_file" and not self.fs.can_read(abs_path):
                return {"error": f"Read not permitted: {abs_path}"}

            if tool_name == "write_file" and not self.fs.can_write(abs_path):
                return {"error": f"Write not permitted: {abs_path}"}

        result = run_tool(tool_name, args)

        if tool_name == "write_file" and "error" not in result:
            log_event(
                "info",
                "filesystem",
                "write_receipt",
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "path": os.path.abspath(args["path"]),
                    "bytes": len(args["content"].encode("utf-8")),
                    "operation": "write_file",
                },
            )

        return result
