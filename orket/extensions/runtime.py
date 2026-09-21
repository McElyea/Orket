from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.application.services.runtime_result_projection import require_runtime_success, runtime_result_payload
from orket.orchestration.engine import OrchestrationEngine

from .contracts import RunAction


@dataclass(frozen=True)
class RunContext:
    workspace: Path
    department: str


class ExtensionEngineAdapter:
    def __init__(self, context: RunContext, *, construction_inputs: RuntimeConstructionInputs | None = None):
        require_sync_context(code="E_EXTENSION_ENGINE_REQUIRES_ASYNC_OWNER")
        self.context = context
        self.engine = OrchestrationEngine(context.workspace, context.department, construction_inputs=construction_inputs)

    @classmethod
    @asynccontextmanager
    async def open(cls, context: RunContext):
        """Capture bootstrap inputs and retain construction, actions and required close."""
        workspace, department = Path(context.workspace), context.department
        inputs = await RuntimeConstructionInputs.capture_async()
        workspace = workspace if workspace.is_absolute() else inputs.invocation_root / workspace
        construct = partial(cls, RunContext(workspace, department), construction_inputs=inputs)
        async with open_runtime_owner(construct, label="legacy-action-engine-construction") as owner:
            yield owner

    async def close(self) -> None:
        await self.engine.close()

    async def execute_action(self, action: RunAction) -> dict[str, Any]:
        op = str(action.op or "").strip().lower()
        target = str(action.target or "").strip()
        params = dict(action.params or {})
        if not target:
            raise ValueError("RunAction target is required")

        canonical_op = "run_card" if op in {"run_epic", "run_issue", "run_rock"} else op

        # Legacy action ops normalize onto the canonical card surface.
        if canonical_op == "run_card":
            result = await self.engine.run_card(target, **params)
            return runtime_result_payload(require_runtime_success(result))

        raise ValueError(f"Unsupported run action op '{action.op}'")
