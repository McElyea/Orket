from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_script_module(name: str, relative_path: str):
    path = Path(relative_path).resolve()
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _report(compliance_a: float, compliance_b: float, passed_a: int, runs_a: int, passed_b: int, runs_b: int):
    return {
        "model_compliance": {
            "m1": {"compliance_score": compliance_a},
            "m2": {"compliance_score": compliance_b},
        },
        "completion_by_model": {
            "m1": {"runs": runs_a, "passed": passed_a},
            "m2": {"runs": runs_b, "passed": passed_b},
        },
    }


def test_policy_release_gate_passes_on_compliance_improvement():
    mod = _load_script_module("check_policy_release_gate_a", "scripts/check_policy_release_gate.py")
    previous = _report(80.0, 84.0, 1, 2, 1, 2)
    current = _report(86.0, 88.0, 1, 2, 1, 2)
    result = mod.evaluate_policy_release_gate(previous_report=previous, current_report=current)
    assert result["ok"] is True
    assert result["checks"]["compliance_delta_ok"] is True


def test_policy_release_gate_passes_on_success_rate_improvement():
    mod = _load_script_module("check_policy_release_gate_b", "scripts/check_policy_release_gate.py")
    previous = _report(80.0, 80.0, 0, 2, 0, 2)
    current = _report(80.0, 80.0, 2, 2, 2, 2)
    result = mod.evaluate_policy_release_gate(previous_report=previous, current_report=current)
    assert result["ok"] is True
    assert result["checks"]["success_rate_delta_ok"] is True


def test_policy_release_gate_fails_when_no_measurable_gain():
    mod = _load_script_module("check_policy_release_gate_c", "scripts/check_policy_release_gate.py")
    previous = _report(90.0, 90.0, 2, 2, 2, 2)
    current = _report(90.0, 90.0, 2, 2, 2, 2)
    result = mod.evaluate_policy_release_gate(previous_report=previous, current_report=current)
    assert result["ok"] is False
