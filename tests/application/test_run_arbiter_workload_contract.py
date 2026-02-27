from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1, parse_workload_contract


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    scripts_dir = str(path.parent.resolve())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_compile_plan_emits_workload_contract(tmp_path: Path) -> None:
    module = _load_script_module("run_arbiter_workload_contract", "scripts/run_arbiter.py")
    arbiter = module.RunArbiter(
        plan_out=tmp_path / "out" / "arbiter_plan.json",
        error_out=tmp_path / "out" / "arbiter_error.json",
    )
    plan = arbiter.compile_plan(
        python_bin="python",
        base_spec=tmp_path / "base_spec.json",
        out_dir=tmp_path / "out",
        index_out=tmp_path / "out" / "index.json",
        provenance_out=tmp_path / "out" / "provenance.json",
        require_provenance=True,
        require_clean_git=False,
        architects=["architect:model"],
        auditors=["auditor:model"],
    )
    workload = parse_workload_contract(plan["workload_contract"])
    assert workload.workload_contract_version == WORKLOAD_CONTRACT_VERSION_V1
    assert workload.workload_type == "odr"
    assert len(workload.units) == 1
    assert str((tmp_path / "out" / "provenance.json").as_posix()) in workload.provenance_targets
    assert "shape" in workload.validators
    assert "trace" in workload.validators
    assert "leak" in workload.validators


def test_compile_plan_workload_contract_omits_provenance_target_when_disabled(tmp_path: Path) -> None:
    module = _load_script_module("run_arbiter_workload_contract_no_prov", "scripts/run_arbiter.py")
    arbiter = module.RunArbiter(
        plan_out=tmp_path / "out" / "arbiter_plan.json",
        error_out=tmp_path / "out" / "arbiter_error.json",
    )
    plan = arbiter.compile_plan(
        python_bin="python",
        base_spec=tmp_path / "base_spec.json",
        out_dir=tmp_path / "out",
        index_out=tmp_path / "out" / "index.json",
        provenance_out=None,
        require_provenance=False,
        require_clean_git=False,
        architects=["architect:model"],
        auditors=["auditor:model"],
    )
    workload = parse_workload_contract(plan["workload_contract"])
    assert workload.provenance_targets == []
