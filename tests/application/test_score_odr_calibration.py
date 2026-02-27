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


def test_score_uses_weighted_loss_formula() -> None:
    module = _load_script_module("score_odr_calibration_test", "scripts/score_odr_calibration.py")
    eval_payload = {
        "runs": [
            {"run_id": "a", "final_outcome_eval": "CONVERGED_RESOLVED", "rounds": [1]},
            {"run_id": "b", "final_outcome_eval": "MAX_ROUNDS", "rounds": [1, 2, 3, 4]},
            {"run_id": "c", "final_outcome_eval": "MAX_ROUNDS", "rounds": [1, 2]},
            {"run_id": "d", "final_outcome_eval": "LOOP_DETECTED", "rounds": [1, 2]},
        ]
    }
    gold_payload = {
        "runs": [
            {"run_id": "a", "first_good_enough_round": 2, "final_outcome_gold": "CONVERGED_RESOLVED"},
            {"run_id": "b", "first_good_enough_round": 2, "final_outcome_gold": "CONVERGED_RESOLVED"},
            {"run_id": "c", "first_good_enough_round": None, "final_outcome_gold": "LOOP_DETECTED"},
            {"run_id": "d", "first_good_enough_round": None, "final_outcome_gold": "FORMAT_VIOLATION"},
        ]
    }
    report = module.score(eval_payload, gold_payload)
    # false_stop_rate=1/2, overrun_rate=1/2, loop_miss_rate=1/1, format_miss_rate=1/1
    # loss = 2*0.5 + 0.5 + 1 + 1 = 3.5
    assert abs(report["loss"] - 3.5) < 1e-9
