"""Capture prompt command inputs before owning the complete model-file operation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.prompt_asset_store import PromptAssetStore
from orket.application.services.prompt_asset_commands import PromptAssetCommands
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.prompt_assets import VALID_STATUSES


@dataclass(frozen=True)
class PromptAssetService:
    statuses = VALID_STATUSES
    root: Path
    inputs: RuntimeInputService = field(default_factory=RuntimeInputService)

    def __post_init__(self):
        if not self.root.is_absolute():
            raise ValueError("E_PROMPT_ROOT_ABSOLUTE_REQUIRED")

    async def execute(self, operation: str, **options: Any) -> Any:
        captured = deepcopy(options)
        explicit = captured.pop("as_of", None)
        anchor = date.fromisoformat(explicit) if isinstance(explicit, str) else explicit
        if anchor is None:
            anchor = self.inputs.utc_now().date()
        if type(anchor) is not date:
            raise ValueError("E_PROMPT_DATE_INVALID")
        return await run_owned_thread(lambda: self._execute(operation, captured, anchor), label="prompt-command")

    def _execute(self, operation: str, options: dict[str, Any], anchor: date) -> Any:
        store = PromptAssetStore(self.root)
        commands = PromptAssetCommands(store, anchor)
        handlers = {"list": commands.list, "show": commands.show, "lint": commands.lint,
                    "resolve": commands.resolve, "update": commands.update,
                    "stale": commands.stale, "enforce_sla": commands.enforce_sla}
        if operation not in handlers:
            raise ValueError(f"Unsupported prompt operation: {operation}")
        with store.guard():
            report_path = options.pop("promotion_report_path", None)
            if report_path:
                options["promotion_report"] = store.read_report(Path(report_path))
            return handlers[operation](**options)
