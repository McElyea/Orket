from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script_module(name: str, relative_path: str):
    path = Path(relative_path).resolve()
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_enforcement_flip_gate_passes_when_all_checks_green():
    mod = _load_script_module(
        "check_security_enforcement_flip_gate_a",
        "scripts/security/check_security_enforcement_flip_gate.py",
    )
    result = mod.evaluate_enforcement_flip_gate(
        ci_failure_payload={"summary": {"p0": 0}},
        compat_warnings_payload={"warning_count": 0},
        compat_expiry_payload={"ok": True},
        security_regression_payload={"ok": True},
    )
    assert result["ok"] is True
    assert result["failures"] == []


def test_enforcement_flip_gate_fails_when_any_check_fails():
    mod = _load_script_module(
        "check_security_enforcement_flip_gate_b",
        "scripts/security/check_security_enforcement_flip_gate.py",
    )
    result = mod.evaluate_enforcement_flip_gate(
        ci_failure_payload={"summary": {"p0": 1}},
        compat_warnings_payload={"warning_count": 2},
        compat_expiry_payload={"ok": False},
        security_regression_payload={"ok": False},
    )
    assert result["ok"] is False
    assert len(result["failures"]) == 4

