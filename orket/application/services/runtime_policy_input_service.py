"""Capture policy observations once; retain asynchronous reads through interruption."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.adapters.storage.runtime_policy_reader import read_runtime_policy_document
from orket.application.services.microservices_acceptance_reports import (
    normalize_microservices_pilot_stability_report,
    normalize_microservices_unlock_report,
)
from orket.application.services.runtime_policy import (
    DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT,
    DEFAULT_MICROSERVICES_UNLOCK_REPORT,
)
from orket.application.services.runtime_policy_inputs import (
    ArchitecturePolicySnapshot,
    RuntimePolicySnapshot,
    freeze_policy_environment,
)


class RuntimePolicyInputService:
    def __init__(self, *, environment: Mapping[str, str], invocation_root: Path) -> None:
        if not invocation_root.is_absolute():
            raise ValueError("E_RUNTIME_POLICY_ROOT_ABSOLUTE_REQUIRED")
        self.environment = freeze_policy_environment(environment)
        self.invocation_root = invocation_root

    def _path(self, name: str, default: str) -> Path:
        selected = Path(str(self.environment.get(name) or default))
        return selected if selected.is_absolute() else self.invocation_root / selected

    def _architecture(self, read) -> ArchitecturePolicySnapshot:
        override = str(self.environment.get("ORKET_ENABLE_MICROSERVICES") or "").strip().lower()
        if override in {"1", "true", "yes", "on"}:
            return ArchitecturePolicySnapshot(True)
        if override in {"0", "false", "no", "off"}:
            return ArchitecturePolicySnapshot(False)
        path = self._path("ORKET_MICROSERVICES_UNLOCK_REPORT", DEFAULT_MICROSERVICES_UNLOCK_REPORT)
        return ArchitecturePolicySnapshot(bool(normalize_microservices_unlock_report(read(path)).get("unlocked")))

    def observe_architecture(self) -> ArchitecturePolicySnapshot:
        require_sync_context(code="E_RUNTIME_POLICY_REQUIRES_ASYNC_OWNER")
        return self._architecture(read_runtime_policy_document)

    async def observe_architecture_async(self) -> ArchitecturePolicySnapshot:
        return await run_owned_thread(self.observe_architecture, label="architecture-policy-observation")

    def _runtime(self) -> RuntimePolicySnapshot:
        documents = {}

        def read(path):
            if path not in documents:
                documents[path] = read_runtime_policy_document(path)
            return documents[path]

        architecture = self._architecture(read)
        pilot_path = self._path("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", DEFAULT_MICROSERVICES_PILOT_STABILITY_REPORT)
        stable = bool(normalize_microservices_pilot_stability_report(read(pilot_path)).get("stable"))
        return RuntimePolicySnapshot(architecture, stable, self.environment)

    async def observe_runtime(self) -> RuntimePolicySnapshot:
        return await run_owned_thread(self._runtime, label="runtime-policy-observation")
