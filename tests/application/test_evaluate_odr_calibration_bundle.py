from __future__ import annotations

import importlib.util
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
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_evaluator_emits_warning_when_conflict_disappears_without_marker() -> None:
    module = _load_script_module("evaluate_odr_calibration_bundle_test", "scripts/evaluate_odr_calibration_bundle.py")
    bundle = {
        "runs": [
            {
                "run_id": "r1",
                "scenario_id": "s1",
                "category": "bad",
                "model_matrix": {"architect": "a", "auditor": "b"},
                "seed_decisions": {},
                "rounds": [
                    {
                        "t": 1,
                        "sections": {
                            "REQUIREMENT": "Must retain logs for 180 days. Must not retain logs for 180 days.",
                            "CHANGELOG": ["Introduce conflict."],
                            "ASSUMPTIONS": [],
                            "OPEN_QUESTIONS": [],
                        },
                        "parse_ok": True,
                        "code_leak_hit": False,
                        "notes": [],
                    },
                    {
                        "t": 2,
                        "sections": {
                            "REQUIREMENT": "Must retain logs for 180 days.",
                            "CHANGELOG": ["Removed contradictory line without marker."],
                            "ASSUMPTIONS": [],
                            "OPEN_QUESTIONS": [],
                        },
                        "parse_ok": True,
                        "code_leak_hit": False,
                        "notes": [],
                    },
                ],
            }
        ]
    }

    report = module.evaluate_bundle(bundle)
    assert report["run_count"] == 1
    rounds = report["runs"][0]["rounds"]
    assert rounds[1]["conflict_active"] is True
    assert any(item.startswith("WARN_CONFLICT_CLEAR_MARKER_MISSING:") for item in rounds[1]["warnings"])


def test_evaluator_marks_format_violation_on_parse_or_code_leak() -> None:
    module = _load_script_module("evaluate_odr_calibration_bundle_test_fmt", "scripts/evaluate_odr_calibration_bundle.py")
    bundle = {
        "runs": [
            {
                "run_id": "r2",
                "scenario_id": "s2",
                "category": "bad",
                "model_matrix": {"architect": "a", "auditor": "b"},
                "seed_decisions": {},
                "rounds": [
                    {
                        "t": 1,
                        "sections": {
                            "REQUIREMENT": "Must store profile data locally.",
                            "CHANGELOG": ["Baseline"],
                            "ASSUMPTIONS": [],
                            "OPEN_QUESTIONS": [],
                        },
                        "parse_ok": False,
                        "code_leak_hit": True,
                        "notes": [],
                    }
                ],
            }
        ]
    }
    report = module.evaluate_bundle(bundle)
    assert report["runs"][0]["final_outcome_eval"] == "FORMAT_VIOLATION"
