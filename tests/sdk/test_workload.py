from __future__ import annotations

from pathlib import Path

import pytest

from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.result import WorkloadResult
from orket_extension_sdk.workload import WorkloadContext, run_workload


class _GoodWorkload:
    def run(self, ctx: WorkloadContext, payload: dict[str, object]) -> WorkloadResult:
        return WorkloadResult(ok=True, output={"workload_id": ctx.workload_id, **payload})


class _BadWorkload:
    def run(self, ctx: WorkloadContext, payload: dict[str, object]) -> dict[str, object]:
        return {"ok": True}


def _ctx(tmp_path: Path) -> WorkloadContext:
    registry = CapabilityRegistry()
    return WorkloadContext(
        extension_id="ext",
        workload_id="work",
        run_id="r1",
        workspace_root=tmp_path,
        input_dir=tmp_path,
        output_dir=tmp_path / "out",
        capabilities=registry,
    )


def test_run_workload_validates_result_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="E_SDK_WORKLOAD_RESULT_INVALID"):
        run_workload(_BadWorkload(), _ctx(tmp_path), {})


def test_run_workload_returns_result(tmp_path: Path) -> None:
    result = run_workload(_GoodWorkload(), _ctx(tmp_path), {"k": "v"})

    assert result.ok is True
    assert result.output["workload_id"] == "work"
