from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Protocol, Sequence


@dataclass(frozen=True)
class RunAction:
    op: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunPlan:
    workload_id: str
    workload_version: str
    actions: tuple[RunAction, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "workload_version": self.workload_version,
            "actions": [asdict(action) for action in self.actions],
            "metadata": self.metadata,
        }

    def plan_hash(self) -> str:
        canonical = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class WorkloadValidator(Protocol):
    def __call__(self, run_result: dict[str, Any], artifact_root: str) -> Sequence[str]:
        ...


class Workload(Protocol):
    workload_id: str
    workload_version: str

    def compile(self, input_config: dict[str, Any]) -> RunPlan:
        ...

    def validators(self) -> Sequence[Callable[[dict[str, Any], str], Sequence[str]]]:
        ...

    def summarize(self, run_artifacts: dict[str, Any]) -> dict[str, Any]:
        ...

    def required_materials(self) -> Sequence[str]:
        ...


class ExtensionRegistry(Protocol):
    def register_workload(self, workload: Workload) -> None:
        ...
