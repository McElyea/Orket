from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.orchestration.engine import OrchestrationEngine

from .contracts import RunAction


@dataclass(frozen=True)
class RunContext:
    workspace: Path
    department: str


class ExtensionEngineAdapter:
    def __init__(self, context: RunContext):
        self.context = context
        self.engine = OrchestrationEngine(context.workspace, context.department)

    async def execute_action(self, action: RunAction) -> dict[str, Any]:
        op = str(action.op or "").strip().lower()
        target = str(action.target or "").strip()
        params = dict(action.params or {})
        if not target:
            raise ValueError("RunAction target is required")

        if op == "run_card":
            return await self.engine.run_card(target, **params)
        if op == "run_epic":
            return {"transcript": await self.engine.run_epic(target, **params)}
        if op == "run_rock":
            return await self.engine.run_rock(target, **params)
        if op == "run_issue":
            return {"transcript": await self.engine.run_issue(target, **params)}

        raise ValueError(f"Unsupported run action op '{action.op}'")
