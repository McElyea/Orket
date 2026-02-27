from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    scripts_dir = str(path.parent.resolve())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _args(tmp_path: Path, *, base_spec: Path, provenance_out: str = "") -> argparse.Namespace:
    return argparse.Namespace(
        base_spec=str(base_spec),
        architect_models="architect:model",
        auditor_models="auditor:model",
        out_dir=str(tmp_path / "out"),
        index_out=str(tmp_path / "out" / "index.json"),
        provenance_out=provenance_out,
        no_provenance_probes=True,
        arbiter_plan_out=str(tmp_path / "out" / "arbiter_plan.json"),
        arbiter_error_out=str(tmp_path / "out" / "arbiter_error.json"),
        require_clean_git=False,
        python_bin="python",
    )


def _valid_run_payload(*, architect: str, auditor: str) -> dict:
    trace = {
        "round": 1,
        "metrics": {
            "code_leak_hit": False,
            "n": 1,
            "diff_ratio": None,
            "sim_prev": None,
            "sim_loop": None,
            "stable_count": 0,
        },
        "stop_reason": None,
    }
    return {
        "run_v": "1.0.0",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "config": {"architect_models": [architect], "auditor_models": [auditor], "rounds": 1},
        "results": [
            {
                "architect_model": architect,
                "auditor_model": auditor,
                "scenarios": [
                    {
                        "scenario_id": "S1",
                        "rounds": [
                            {
                                "round": 1,
                                "odr_trace_record": trace,
                                "state_stop_reason_after_round": None,
                            }
                        ],
                        "final_state": {
                            "history_v": ["req"],
                            "history_round_count": 1,
                            "stable_count": 0,
                            "stop_reason": None,
                            "history_rounds": [trace],
                        },
                    }
                ],
            }
        ],
    }


def test_run_odr_quant_sweep_preflight_fail_closed_blocks_execution(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_odr_quant_sweep_preflight", "scripts/run_odr_quant_sweep.py")
    run_arbiter = sys.modules["run_arbiter"]
    base_spec = tmp_path / "base.json"
    base_spec.write_text(json.dumps({"config": {"rounds": 1}}), encoding="utf-8")
    args = _args(tmp_path, base_spec=base_spec)

    executed: list[list[str]] = []

    def _fake_exec(cmd, check=False, **kwargs):  # noqa: ANN001, ANN003
        executed.append(list(cmd))
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(
        run_arbiter.RunArbiter,
        "_tool_exists",
        staticmethod(lambda value: True if value in {"python", "ollama"} else Path(value).exists()),
    )
    monkeypatch.setattr(run_arbiter.RunArbiter, "_missing_models", lambda self, plan: ["architect:model", "auditor:model"])
    monkeypatch.setattr(module.subprocess, "run", _fake_exec)

    rc = module.run_sweep(args)
    assert rc == 2
    assert executed == []
    error = json.loads((tmp_path / "out" / "arbiter_error.json").read_text(encoding="utf-8"))
    assert error["phase"] == "preflight"
    assert error["code"] == "E_ARB_PREFLIGHT_MISSING_MATERIAL"
    assert "model:architect:model" in error["failures"]
    assert "model:auditor:model" in error["failures"]


def test_run_odr_quant_sweep_arbiter_passes_and_checks_postflight(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_odr_quant_sweep_pass", "scripts/run_odr_quant_sweep.py")
    run_arbiter = sys.modules["run_arbiter"]
    base_spec = tmp_path / "base.json"
    base_spec.write_text(json.dumps({"config": {"rounds": 1}}), encoding="utf-8")
    provenance_out = str(tmp_path / "out" / "provenance.json")
    args = _args(tmp_path, base_spec=base_spec, provenance_out=provenance_out)

    def _fake_exec(cmd, check=False, **kwargs):  # noqa: ANN001, ANN003
        if len(cmd) > 1 and cmd[1] == "scripts/run_odr_live_role_matrix.py":
            out = Path(cmd[cmd.index("--out") + 1])
            architect = cmd[cmd.index("--architect-models") + 1]
            auditor = cmd[cmd.index("--auditor-models") + 1]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(_valid_run_payload(architect=architect, auditor=auditor)), encoding="utf-8")
        if len(cmd) > 1 and cmd[1] == "scripts/generate_odr_provenance.py":
            out = Path(cmd[cmd.index("--out") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"ok": True}), encoding="utf-8")

        class Result:
            returncode = 0

        return Result()

    def _fake_generate_index(*, input_dir: Path, output_path: Path):  # noqa: ANN001
        payload = {"run_count": 1, "root": str(input_dir)}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(
        run_arbiter.RunArbiter,
        "_tool_exists",
        staticmethod(lambda value: True if value in {"python", "ollama"} else Path(value).exists()),
    )
    monkeypatch.setattr(run_arbiter.RunArbiter, "_missing_models", lambda self, plan: [])
    monkeypatch.setattr(module.subprocess, "run", _fake_exec)
    monkeypatch.setattr(module.odr_index, "generate_index", _fake_generate_index)

    rc = module.run_sweep(args)
    assert rc == 0
    assert Path(args.index_out).exists()
    assert Path(args.provenance_out).exists()
    plan = json.loads(Path(args.arbiter_plan_out).read_text(encoding="utf-8"))
    assert plan["schema_version"] == "odr.run_arbiter.plan.v1"
    assert str(Path(args.index_out).as_posix()) in plan["expected_artifacts"]
    assert str(Path(args.provenance_out).as_posix()) in plan["expected_artifacts"]
    assert plan["workload_contract"]["workload_contract_version"] == "workload.contract.v1"
    assert plan["workload_contract"]["workload_type"] == "odr"
    assert isinstance(plan["workload_contract"]["units"], list)
    assert isinstance(plan["workload_contract"]["required_materials"], list)
    assert not Path(args.arbiter_error_out).exists()


def test_run_odr_quant_sweep_arbiter_leak_validator_emits_error(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_odr_quant_sweep_leak", "scripts/run_odr_quant_sweep.py")
    run_arbiter = sys.modules["run_arbiter"]
    base_spec = tmp_path / "base.json"
    base_spec.write_text(json.dumps({"config": {"rounds": 1}}), encoding="utf-8")
    args = _args(tmp_path, base_spec=base_spec)

    def _fake_exec(cmd, check=False, **kwargs):  # noqa: ANN001, ANN003
        if len(cmd) > 1 and cmd[1] == "scripts/run_odr_live_role_matrix.py":
            out = Path(cmd[cmd.index("--out") + 1])
            architect = cmd[cmd.index("--architect-models") + 1]
            auditor = cmd[cmd.index("--auditor-models") + 1]
            payload = _valid_run_payload(architect=architect, auditor=auditor)
            payload["results"][0]["scenarios"][0]["rounds"][0]["odr_trace_record"]["stop_reason"] = "CODE_LEAK"
            payload["results"][0]["scenarios"][0]["rounds"][0]["odr_trace_record"]["metrics"]["code_leak_hit"] = True
            payload["results"][0]["scenarios"][0]["final_state"]["history_rounds"][0]["stop_reason"] = "CODE_LEAK"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload), encoding="utf-8")

        class Result:
            returncode = 0

        return Result()

    def _fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Index generation should not run after leak validator fails.")

    monkeypatch.setattr(
        run_arbiter.RunArbiter,
        "_tool_exists",
        staticmethod(lambda value: True if value in {"python", "ollama"} else Path(value).exists()),
    )
    monkeypatch.setattr(run_arbiter.RunArbiter, "_missing_models", lambda self, plan: [])
    monkeypatch.setattr(module.subprocess, "run", _fake_exec)
    monkeypatch.setattr(module.odr_index, "generate_index", _fail_if_called)

    rc = module.run_sweep(args)
    assert rc == 2
    error = json.loads(Path(args.arbiter_error_out).read_text(encoding="utf-8"))
    assert error["phase"] == "execution"
    assert error["code"] == "E_ARB_VALIDATOR_LEAK"


def test_run_odr_quant_sweep_require_clean_git_fails_when_dirty(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module("run_odr_quant_sweep_git_gate", "scripts/run_odr_quant_sweep.py")
    run_arbiter = sys.modules["run_arbiter"]
    base_spec = tmp_path / "base.json"
    base_spec.write_text(json.dumps({"config": {"rounds": 1}}), encoding="utf-8")
    args = _args(tmp_path, base_spec=base_spec)
    args.require_clean_git = True

    monkeypatch.setattr(
        run_arbiter.RunArbiter,
        "_tool_exists",
        staticmethod(lambda value: True if value in {"python", "ollama"} else Path(value).exists()),
    )
    monkeypatch.setattr(run_arbiter.RunArbiter, "_missing_models", lambda self, plan: [])
    monkeypatch.setattr(run_arbiter.RunArbiter, "_git_is_clean", staticmethod(lambda: False))

    rc = module.run_sweep(args)
    assert rc == 2
    error = json.loads(Path(args.arbiter_error_out).read_text(encoding="utf-8"))
    assert error["phase"] == "preflight"
    assert "git:dirty_worktree" in error["failures"]
