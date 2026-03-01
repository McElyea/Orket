from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .capabilities import CapabilityRegistry
from .result import WorkloadResult


@dataclass(slots=True)
class WorkloadContext:
    extension_id: str
    workload_id: str
    run_id: str
    workspace_root: Path
    input_dir: Path
    output_dir: Path
    capabilities: CapabilityRegistry
    seed: int = 0
    config: dict[str, Any] = field(default_factory=dict)


class Workload(Protocol):
    def run(self, ctx: WorkloadContext, payload: dict[str, Any]) -> WorkloadResult:
        ...


def run_workload(workload: Workload, ctx: WorkloadContext, payload: dict[str, Any]) -> WorkloadResult:
    result = workload.run(ctx, payload)
    if not isinstance(result, WorkloadResult):
        raise ValueError("E_SDK_WORKLOAD_RESULT_INVALID")
    return result
