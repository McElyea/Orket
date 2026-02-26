from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .report import build_report
from .scoring import score_run
from .spec import expand_run_refs, normalize_spec, spec_hash


def run_experiment_v1(request: Dict[str, Any]) -> Dict[str, Any]:
    spec = normalize_spec(request)
    digest = spec_hash(spec)
    refs = expand_run_refs(spec)
    provided = _index_results(request.get("run_results"))

    rows: List[Dict[str, Any]] = []
    for ref in refs:
        key = _result_key(
            scenario_id=ref.scenario_id,
            seed=ref.seed,
            repeat_index=ref.repeat_index,
            model_map=ref.model_map,
        )
        result = dict(provided.get(key) or {})
        if not result:
            result = _missing_result()
        scored = score_run(result, spec.get("scoring", {}))
        rows.append(
            {
                "run_id": ref.run_id,
                "scenario_id": ref.scenario_id,
                "seed": ref.seed,
                "repeat_index": ref.repeat_index,
                "model_map": dict(ref.model_map),
                "result": result,
                **scored,
            }
        )

    return build_report(spec_hash=digest, spec=spec, run_rows=rows)


def _result_key(*, scenario_id: str, seed: int, repeat_index: int, model_map: Dict[str, str]) -> Tuple[Any, ...]:
    return (
        str(scenario_id),
        int(seed),
        int(repeat_index),
        tuple((role, str(model_map.get(role))) for role in sorted(model_map.keys())),
    )


def _index_results(raw: Any) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    rows: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        model_map = item.get("model_map")
        if not isinstance(model_map, dict) or not model_map:
            continue
        scenario_id = str(item.get("scenario_id") or "").strip()
        if not scenario_id:
            continue
        try:
            seed = int(item.get("seed", 0))
            repeat_index = int(item.get("repeat_index", 0))
        except (TypeError, ValueError):
            continue
        key = _result_key(
            scenario_id=scenario_id,
            seed=seed,
            repeat_index=repeat_index,
            model_map={str(k): str(v) for k, v in model_map.items()},
        )
        rows[key] = _normalize_result(item.get("result"))
    return rows


def _normalize_result(value: Any) -> Dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    normalized = {
        "forbidden_hits": int(data.get("forbidden_hits", 0)),
        "anti_hallucination_hits": int(data.get("anti_hallucination_hits", 0)),
        "reopened_issues": int(data.get("reopened_issues", 0)),
        "missing_required_sections": int(data.get("missing_required_sections", 0)),
        "unresolved_counts": [int(v) for v in (data.get("unresolved_counts") or [])],
        "rounds_to_zero": int(data.get("rounds_to_zero", 0)),
        "oscillation_hits": int(data.get("oscillation_hits", 0)),
    }
    return normalized


def _missing_result() -> Dict[str, Any]:
    return {
        "forbidden_hits": 0,
        "anti_hallucination_hits": 1,
        "reopened_issues": 0,
        "missing_required_sections": 0,
        "unresolved_counts": [],
        "rounds_to_zero": 0,
        "oscillation_hits": 0,
    }
