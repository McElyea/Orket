from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

from orket.kernel.v1.canon import canonical_bytes


@dataclass(frozen=True)
class ExperimentRunRef:
    run_id: str
    scenario_id: str
    seed: int
    repeat_index: int
    model_map: Dict[str, str]


def normalize_spec(request: Dict[str, Any]) -> Dict[str, Any]:
    experiment_id = str(request.get("experiment_id") or "").strip()
    if not experiment_id:
        raise ValueError("experiment_id is required")

    task = str(request.get("task") or "").strip() or "unknown"
    matrix = request.get("matrix")
    if not isinstance(matrix, dict) or not matrix:
        raise ValueError("matrix must be a non-empty mapping of role -> model list")

    normalized_matrix: Dict[str, List[str]] = {}
    for role in sorted(str(k).strip() for k in matrix.keys() if str(k).strip()):
        values = matrix.get(role)
        if not isinstance(values, list) or not values:
            raise ValueError(f"matrix role '{role}' must map to a non-empty model list")
        models = sorted(str(item).strip() for item in values if str(item).strip())
        if not models:
            raise ValueError(f"matrix role '{role}' has no usable models")
        normalized_matrix[role] = models

    scenarios_raw = request.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("scenarios must be a non-empty list")
    normalized_scenarios: List[Dict[str, Any]] = []
    seen_scenarios = set()
    for row in scenarios_raw:
        if not isinstance(row, dict):
            raise ValueError("scenario rows must be objects")
        scenario_id = str(row.get("scenario_id") or row.get("id") or "").strip()
        if not scenario_id:
            raise ValueError("scenario row missing scenario_id")
        if scenario_id in seen_scenarios:
            raise ValueError(f"duplicate scenario_id '{scenario_id}'")
        seen_scenarios.add(scenario_id)
        normalized_scenarios.append({"scenario_id": scenario_id})
    normalized_scenarios.sort(key=lambda item: item["scenario_id"])

    seeds_raw = request.get("seeds")
    if isinstance(seeds_raw, list) and seeds_raw:
        seeds = sorted({int(value) for value in seeds_raw})
    elif isinstance(seeds_raw, dict):
        start = int(seeds_raw.get("start", 0))
        stop = int(seeds_raw.get("stop", start))
        step = int(seeds_raw.get("step", 1))
        if step <= 0:
            raise ValueError("seeds.step must be > 0")
        seeds = list(range(start, stop + 1, step))
    else:
        seeds = [0]
    if not seeds:
        raise ValueError("seeds expansion produced no values")

    repeats = int(request.get("repeats_per_run", 1))
    if repeats < 1:
        raise ValueError("repeats_per_run must be >= 1")

    scoring = request.get("scoring")
    if not isinstance(scoring, dict):
        scoring = {}

    run_config = request.get("run_config")
    if not isinstance(run_config, dict):
        run_config = {}

    return {
        "experiment_id": experiment_id,
        "task": task,
        "matrix": normalized_matrix,
        "scenarios": normalized_scenarios,
        "seeds": seeds,
        "repeats_per_run": repeats,
        "run_config": run_config,
        "scoring": scoring,
    }


def spec_hash(spec: Dict[str, Any]) -> str:
    payload = canonical_bytes(spec)
    return hashlib.sha256(payload).hexdigest()


def expand_model_maps(matrix: Dict[str, List[str]]) -> List[Dict[str, str]]:
    role_names = sorted(matrix.keys())
    maps: List[Dict[str, str]] = []

    def _walk(index: int, current: Dict[str, str]) -> None:
        if index >= len(role_names):
            maps.append(dict(current))
            return
        role = role_names[index]
        for model in matrix[role]:
            current[role] = model
            _walk(index + 1, current)
        current.pop(role, None)

    _walk(0, {})
    return maps


def run_identity(
    *,
    experiment_id: str,
    scenario_id: str,
    seed: int,
    repeat_index: int,
    model_map: Dict[str, str],
) -> str:
    material = {
        "experiment_id": experiment_id,
        "scenario_id": scenario_id,
        "seed": int(seed),
        "repeat_index": int(repeat_index),
        "model_map": {k: model_map[k] for k in sorted(model_map.keys())},
    }
    digest = hashlib.sha256(canonical_bytes(material)).hexdigest()
    return digest


def expand_run_refs(spec: Dict[str, Any]) -> List[ExperimentRunRef]:
    refs: List[ExperimentRunRef] = []
    model_maps = expand_model_maps(spec["matrix"])
    for scenario in spec["scenarios"]:
        scenario_id = scenario["scenario_id"]
        for seed in spec["seeds"]:
            for model_map in model_maps:
                for repeat_index in range(spec["repeats_per_run"]):
                    run_id = run_identity(
                        experiment_id=spec["experiment_id"],
                        scenario_id=scenario_id,
                        seed=int(seed),
                        repeat_index=repeat_index,
                        model_map=model_map,
                    )
                    refs.append(
                        ExperimentRunRef(
                            run_id=run_id,
                            scenario_id=scenario_id,
                            seed=int(seed),
                            repeat_index=repeat_index,
                            model_map=dict(model_map),
                        )
                    )
    refs.sort(
        key=lambda row: (
            row.scenario_id,
            row.seed,
            tuple((k, row.model_map[k]) for k in sorted(row.model_map)),
            row.repeat_index,
        )
    )
    return refs
