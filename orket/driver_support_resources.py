"""Driver binding for application-owned structural proposals."""
from pathlib import Path
from typing import Any

from orket.application.services.driver_structural_service import DriverStructuralService


class DriverResourceMixin:
    model_root: Path

    async def _execute_structural_change(self, plan: dict[str, Any]) -> str:
        return await DriverStructuralService(self.model_root, self._operator_workspace_root()).execute(plan)
