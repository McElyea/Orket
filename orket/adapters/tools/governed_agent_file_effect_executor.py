from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from orket.adapters.tools.families.filesystem import FileSystemTools
from orket.core.policies.tool_gate import ToolGateValidator


class GovernedAgentFileEffectExecutor:
    """Issue-scoped adapter over the existing tool gate and filesystem tool."""

    def __init__(self, workspace_root: Path, *, tool_gate: ToolGateValidator) -> None:
        if tool_gate is None:
            raise ValueError("Governed file effects require application tool-gate authority")
        self._gate = tool_gate
        self._files = FileSystemTools(workspace_root, [])

    async def observe(self, *, path: str, issue_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._files.read_file(
                {"path": path},
                context={"issue_id": issue_id, "role": "governed-agent"},
            ),
        )

    async def write(self, *, path: str, content: str | dict[str, Any], issue_id: str) -> dict[str, Any]:
        args = {"path": path, "content": content}
        context = {"issue_id": issue_id, "role": "governed-agent"}
        violation = await self._gate.validate("write_file", args, context, ["governed-agent"])
        if violation:
            return {"ok": False, "error": violation}
        return cast(dict[str, Any], await self._files.write_file(args, context=context))


__all__ = ["GovernedAgentFileEffectExecutor"]
