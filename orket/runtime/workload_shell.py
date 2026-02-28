from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from orket.core.contracts import WorkloadContractV1, parse_workload_contract


@dataclass(frozen=True)
class WorkloadShellError(Exception):
    code: str
    message: str
    detail: dict[str, Any]


class SharedWorkloadShell:
    """
    Shared preflight/execute/postflight wrapper for workload.contract.v1 payloads.
    """

    async def execute(
        self,
        *,
        contract_payload: dict[str, Any],
        execute_fn: Callable[[WorkloadContractV1], Awaitable[Any]],
    ) -> Any:
        contract = parse_workload_contract(contract_payload)
        self._preflight(contract)
        result = await execute_fn(contract)
        self._postflight(contract)
        return result

    def _preflight(self, contract: WorkloadContractV1) -> None:
        for material in contract.required_materials:
            if not isinstance(material, dict):
                raise WorkloadShellError(
                    code="E_WORKLOAD_MATERIAL_INVALID",
                    message="required material entry must be an object",
                    detail={"material": material},
                )
            kind = str(material.get("kind", "")).strip().lower()
            value = str(material.get("value", "")).strip()
            required = bool(material.get("required", False))
            if not kind or not value:
                raise WorkloadShellError(
                    code="E_WORKLOAD_MATERIAL_INVALID",
                    message="required material entry must include non-empty kind/value",
                    detail={"material": material},
                )
            if required and kind == "file" and not Path(value).exists():
                raise WorkloadShellError(
                    code="E_WORKLOAD_MATERIAL_MISSING",
                    message="required workload material missing",
                    detail={"kind": kind, "value": value},
                )

    def _postflight(self, contract: WorkloadContractV1) -> None:
        # Keep postflight mechanical and non-blocking for contracts where artifacts are
        # directory roots or materialize asynchronously across execution stages.
        for artifact in contract.expected_artifacts:
            if not isinstance(artifact, str) or not artifact.strip():
                raise WorkloadShellError(
                    code="E_WORKLOAD_ARTIFACT_INVALID",
                    message="expected artifact entries must be non-empty strings",
                    detail={"artifact": artifact},
                )
