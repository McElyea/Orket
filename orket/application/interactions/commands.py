"""Application admission and owned background dispatch for interaction commands."""
from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.workloads import is_builtin_workload, run_builtin_workload, validate_builtin_workload_start

from .manager import InteractionManager

LOGGER = logging.getLogger(__name__)


class InteractionUnavailable(RuntimeError):
    """Workload admission is unavailable before an interaction turn is created."""


@dataclass(frozen=True)
class InteractionCommands:
    manager: InteractionManager
    extensions: Any
    runtime: Any
    project_root: Path

    def _enabled(self) -> None:
        if not self.manager.stream_enabled():
            raise ValueError("Stream events v1 is disabled.")

    async def start(self, session_params: dict[str, Any]) -> dict[str, Any]:
        self._enabled()
        return {"session_id": await self.manager.start(session_params)}

    async def begin(self, session_id: str, *, workload_id: str, input_config: dict[str, Any],
                    turn_params: dict[str, Any], department: str, workspace: str) -> dict[str, Any]:
        self._enabled()
        config, params = deepcopy(input_config), deepcopy(turn_params)
        workload_id, department, workspace = str(workload_id).strip(), str(department), str(workspace)
        # Model admission currently reads provider settings without file I/O.
        # Preserve its pre-await observation until workload configuration migration.
        if workload_id == "model_stream_v1":
            self._validate(workload_id, config, params)
        resolved, context_inputs, builtin = await run_owned_thread(
            lambda: self._prepare(workload_id, config, params, department, workspace), label="interaction-preflight",
        )
        turn_id = await self.manager.begin_turn(session_id, config, params, context_inputs=context_inputs)
        try:
            context = await self.manager.create_context(session_id, turn_id)
            self.manager.adopt_workload(session_id, turn_id, lambda: self.runtime.start_background(
                lambda: self._run(session_id, turn_id, workload_id, config, params,
                                  department, resolved, builtin, context)))
        except (asyncio.CancelledError, RuntimeError, ValueError, TypeError):
            await self.manager.abort(session_id, turn_id, reason="dispatch_not_adopted")
            raise
        return {"session_id": session_id, "turn_id": turn_id}

    def _prepare(self, workload_id, config, params, department, workspace):
        if not workload_id:
            raise ValueError("workload_id is required")
        builtin = is_builtin_workload(workload_id)
        extension = self.extensions.has_manifest_entry(workload_id)
        if not builtin and not extension:
            raise ValueError(f"Unknown workload '{workload_id}'. Built-in workloads: "
                             "stream_test_v1, model_stream_v1, rulesim_v0, marshaller_v0.")
        capabilities = []
        if builtin:
            if workload_id != "model_stream_v1":
                self._validate(workload_id, config, params)
        else:
            capabilities = list(self.extensions.required_capabilities_for_workload(workload_id))
        root = self.project_root.resolve()
        path = Path(workspace)
        resolved = (path if path.is_absolute() else root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Invalid workspace: path escapes workspace root.")
        context = {"input_config": config, "turn_params": params, "workload_id": workload_id,
                   "department": department, "workspace": str(resolved)}
        if extension:
            context["required_capabilities"] = capabilities
        return resolved, context, builtin

    @staticmethod
    def _validate(workload_id, config, params):
        try:
            validate_builtin_workload_start(workload_id=workload_id, input_config=config, turn_params=params)
        except RuntimeError as exc:
            raise InteractionUnavailable(str(exc)) from exc

    async def _run(self, session_id, turn_id, workload_id, config, params, department, workspace, builtin, context):
        try:
            hints = {}
            if builtin:
                hints = await run_builtin_workload(workload_id=workload_id, input_config=config, turn_params=params,
                                                   interaction_context=context)
                if int(hints.get("request_cancel_turn", 0) or 0) > 0:
                    await self.manager.cancel(turn_id, session_id=session_id)
            else:
                await self.extensions.run_workload(workload_id=workload_id, input_config=config, workspace=workspace,
                                                   department=department, interaction_context=context)
            await self.manager.finalize(session_id, turn_id)
            if int(hints.get("post_finalize_wait_ms", 0)) > 0:
                await asyncio.sleep(int(hints["post_finalize_wait_ms"]) / 1000)
        except asyncio.CancelledError:
            await self.manager.abort(session_id, turn_id, reason="workload_interrupted")
            raise
        except Exception as exc:  # background supervisor records failures before fail-closed publication
            LOGGER.error("Interaction workload failed: session=%s turn=%s", session_id, turn_id, exc_info=True)
            await self.manager.abort(session_id, turn_id, reason=str(exc))

    async def finalize(self, session_id: str, turn_id: str) -> dict[str, Any]:
        self._enabled()
        return (await self.manager.finalize(session_id, turn_id, require_workload_result=True)).model_dump()
