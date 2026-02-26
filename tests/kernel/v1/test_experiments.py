from __future__ import annotations

from orket.kernel.v1 import run_experiment
from orket.kernel.v1.experiments.report import report_canonical_bytes
from orket.kernel.v1.experiments.scoring import score_run
from orket.kernel.v1.experiments.spec import expand_run_refs, normalize_spec


def _base_request() -> dict:
    return {
        "experiment_id": "role-matrix-v1",
        "task": "refinement_behavior",
        "matrix": {
            "architect": ["qwen2.5:14b", "llama3.1:8b"],
            "integrity_guard": ["deepseek-r1:32b", "gemma3:27b"],
        },
        "scenarios": [
            {"scenario_id": "missing_constraint"},
            {"scenario_id": "contradiction"},
        ],
        "seeds": [2, 1],
        "repeats_per_run": 2,
        "run_config": {"rounds": 3},
    }


def test_experiment_runner_enumeration_is_stable() -> None:
    spec = normalize_spec(_base_request())
    refs = expand_run_refs(spec)
    assert len(refs) == 32
    keys = [
        (
            ref.scenario_id,
            ref.seed,
            tuple((k, ref.model_map[k]) for k in sorted(ref.model_map.keys())),
            ref.repeat_index,
        )
        for ref in refs
    ]
    assert keys == sorted(keys)


def test_experiment_scoring_pure_function() -> None:
    result = {
        "forbidden_hits": 0,
        "anti_hallucination_hits": 0,
        "reopened_issues": 0,
        "missing_required_sections": 1,
        "unresolved_counts": [2, 1, 0],
        "rounds_to_zero": 3,
        "oscillation_hits": 0,
    }
    left = score_run(result, {"weights": {"missing_section": 10, "converged_bonus": 10}})
    right = score_run(result, {"weights": {"missing_section": 10, "converged_bonus": 10}})
    assert left == right


def test_experiment_report_canonical_bytes_stable() -> None:
    request = _base_request()
    request["run_results"] = [
        {
            "scenario_id": "missing_constraint",
            "seed": 1,
            "repeat_index": 0,
            "model_map": {"architect": "llama3.1:8b", "integrity_guard": "deepseek-r1:32b"},
            "result": {
                "forbidden_hits": 0,
                "anti_hallucination_hits": 0,
                "reopened_issues": 0,
                "missing_required_sections": 0,
                "unresolved_counts": [1, 0],
                "rounds_to_zero": 2,
                "oscillation_hits": 0,
            },
        }
    ]
    report = run_experiment(request)
    a = report_canonical_bytes(report)
    b = report_canonical_bytes(report)
    assert a == b


def test_experiment_nondeterminism_is_measured_as_variance() -> None:
    request = {
        "experiment_id": "variance-check",
        "task": "refinement_behavior",
        "matrix": {"architect": ["qwen2.5:14b"], "integrity_guard": ["deepseek-r1:32b"]},
        "scenarios": [{"scenario_id": "missing_constraint"}],
        "seeds": [1],
        "repeats_per_run": 2,
        "run_results": [
            {
                "scenario_id": "missing_constraint",
                "seed": 1,
                "repeat_index": 0,
                "model_map": {"architect": "qwen2.5:14b", "integrity_guard": "deepseek-r1:32b"},
                "result": {
                    "forbidden_hits": 0,
                    "anti_hallucination_hits": 0,
                    "reopened_issues": 0,
                    "missing_required_sections": 0,
                    "unresolved_counts": [2, 1, 0],
                    "rounds_to_zero": 3,
                    "oscillation_hits": 0,
                },
            },
            {
                "scenario_id": "missing_constraint",
                "seed": 1,
                "repeat_index": 1,
                "model_map": {"architect": "qwen2.5:14b", "integrity_guard": "deepseek-r1:32b"},
                "result": {
                    "forbidden_hits": 0,
                    "anti_hallucination_hits": 0,
                    "reopened_issues": 0,
                    "missing_required_sections": 2,
                    "unresolved_counts": [2, 2, 1],
                    "rounds_to_zero": 0,
                    "oscillation_hits": 1,
                },
            },
        ],
    }
    report = run_experiment(request)
    assert report["run_count"] == 2
    aggregate = report["aggregates_by_model_map"][0]["aggregate"]
    assert aggregate["variance_score"] is not None
    assert float(aggregate["variance_score"]) > 0.0
