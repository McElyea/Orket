"""Own structural board reconciliation effects and truthful adoption events."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_executor_service import run_coroutine_blocking
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.structural_board_store import StructuralBoardStore
from orket.core.contracts.log_event_inputs import capture_log_event_inputs
from orket.core.domain.reconciler import ReconciliationPlan
from orket.core.domain.reconciler import StructuralReconciler as ReconciliationPolicy
from orket.logging import log_event
from orket.project_paths import default_model_root, default_workspace_root


class StructuralReconciliationError(ValueError):
    """Reconciliation could not safely produce all requested structural updates."""


class StructuralReconciler:
    def __init__(self, root_path: Path | None = None, workspace: Path | None = None) -> None:
        self.root_path = Path(root_path) if root_path is not None else None
        self.workspace = Path(workspace) if workspace is not None else None

    def reconcile_all(self) -> ReconciliationPlan:
        """Explicit synchronous CLI/worker entrypoint; refuses a running event loop."""
        return run_coroutine_blocking(self.reconcile())

    async def reconcile(self) -> ReconciliationPlan:
        selected_root, selected_workspace = self.root_path, self.workspace
        root, workspace = capture_file_roots([
            Path() if selected_root is None else selected_root,
            Path() if selected_workspace is None else selected_workspace,
        ])
        return await run_owned_io(partial(self._reconcile, root, workspace,
            default_root=selected_root is None, default_workspace=selected_workspace is None),
            label="structural-reconciliation", preserve_failure=True)

    async def _reconcile(self, root: Path, workspace: Path, *, default_root: bool,
                         default_workspace: bool) -> ReconciliationPlan:
        if default_root:
            root = await run_owned_thread(partial(default_model_root, root), label="structural-model-root")
        if default_workspace:
            workspace = await run_owned_thread(partial(default_workspace_root, workspace), label="structural-workspace")
        await self._event("reconciler_start", {"root_path": str(root)}, workspace)
        store = StructuralBoardStore(root)
        plan = ReconciliationPolicy.plan(await store.snapshot())
        if plan.problems:
            detail = "; ".join(f"{problem.relative_path}: {problem.detail}" for problem in plan.problems)
            raise StructuralReconciliationError(detail)
        for update in plan.writes:
            await store.apply(update)
            for adoption in plan.adoptions:
                if adoption.target_path != update.relative_path:
                    continue
                kind = "epic" if adoption.kind == "epics" else "issue"
                target = "rock" if kind == "epic" else "epic"
                await self._event(
                    f"reconciler_orphan_{kind}_adopted",
                    {
                        f"{kind}_id": adoption.name,
                        "department": adoption.department,
                        f"target_{target}": adoption.target_id,
                    },
                    workspace,
                )
        return plan

    @staticmethod
    async def _event(name: str, payload: dict, workspace: Path) -> None:
        name, payload = capture_log_event_inputs(name, payload)
        await run_owned_thread(partial(log_event, name, payload, workspace=workspace), label=f"structural-event:{name}")
