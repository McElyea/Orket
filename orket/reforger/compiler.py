from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.reforger.routes import (
    ROUTE_ID_META_BREAKER_V0,
    ROUTE_ID_TEXTMYSTERY_PERSONA_V0,
    MetaBreakerRouteV0,
    TextMysteryPersonaRouteV0,
)

ALLOWED_PATCH_SURFACE = ("/banks", "/entities", "/rules/defaults", "/archetypes", "/balance")


@dataclass(frozen=True)
class CompilerRunResult:
    ok: bool
    hard_fail_count: int
    best_score: float
    best_candidate_id: str
    artifact_root: Path
    materialized_root: Path


def _json_sha(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_manifest(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for item in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: str(p).replace("\\", "/")):
        rel = str(item.relative_to(root)).replace("\\", "/")
        rows[rel] = _file_sha(item)
    return rows


def _resolve_route(route_id: str) -> Any:
    if route_id == ROUTE_ID_TEXTMYSTERY_PERSONA_V0:
        return TextMysteryPersonaRouteV0()
    if route_id == ROUTE_ID_META_BREAKER_V0:
        return MetaBreakerRouteV0()
    raise ValueError(f"unsupported route_id: {route_id}")


def _load_scenario_pack(path: Path, *, mode: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"scenario pack file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("scenario pack must be an object")
    pack_id = str(payload.get("pack_id") or "").strip()
    version = str(payload.get("version") or "").strip()
    pack_mode = str(payload.get("mode") or "").strip()
    tests = payload.get("tests")
    if not pack_id or not version:
        raise ValueError("scenario pack requires non-empty pack_id and version")
    if pack_mode != mode:
        raise ValueError(f"scenario pack mode mismatch: expected {mode}, got {pack_mode or '<empty>'}")
    if not isinstance(tests, list) or not tests:
        raise ValueError("scenario pack requires non-empty tests list")

    normalized_tests: list[dict[str, Any]] = []
    for row in tests:
        if not isinstance(row, dict):
            raise ValueError("scenario pack tests must contain objects")
        test_id = str(row.get("id") or "").strip()
        kind = str(row.get("kind") or "").strip()
        if not test_id or not kind:
            raise ValueError("scenario pack test requires id and kind")
        normalized_tests.append(
            {
                "id": test_id,
                "kind": kind,
                "hard": bool(row.get("hard", False)),
                "weight": float(row.get("weight", 0.0)),
                "params": dict(row.get("params", {})) if isinstance(row.get("params"), dict) else {},
            }
        )
    normalized_tests.sort(key=lambda row: row["id"])
    return {
        "pack_id": pack_id,
        "version": version,
        "mode": pack_mode,
        "tests": normalized_tests,
    }


def _eval_truth_only(blob: dict[str, Any], scenario_pack: dict[str, Any]) -> dict[str, Any]:
    archetypes = blob["banks"]["archetypes"]
    refusal_styles = blob["banks"]["refusal_styles"]
    npcs = blob["entities"]["npcs"]

    checks: list[dict[str, Any]] = []
    for test in scenario_pack.get("tests", []):
        kind = str(test.get("kind") or "")
        params = test.get("params") if isinstance(test.get("params"), dict) else {}
        hard = bool(test.get("hard", False))
        weight = float(test.get("weight", 0.0))
        ok = True
        detail = ""

        if kind == "npc_archetype_exists":
            for npc_id in sorted(npcs):
                archetype = str(npcs[npc_id].get("archetype") or "")
                if archetype not in archetypes:
                    ok = False
                    detail = f"{npc_id} missing archetype {archetype}"
                    break
        elif kind == "npc_refusal_style_exists":
            for npc_id in sorted(npcs):
                style_id = str(npcs[npc_id].get("refusal_style_id") or "")
                if style_id and style_id not in refusal_styles:
                    ok = False
                    detail = f"{npc_id} missing refusal_style {style_id}"
                    break
        elif kind == "refusal_templates_non_empty":
            for sid in sorted(refusal_styles):
                templates = refusal_styles[sid].get("templates")
                if not isinstance(templates, list) or not [t for t in templates if str(t).strip()]:
                    ok = False
                    detail = f"{sid} has empty templates"
                    break
        elif kind == "no_exclamation_rules":
            for aid in sorted(archetypes):
                rules = archetypes[aid].get("rules")
                if isinstance(rules, dict) and bool(rules.get("allow_exclamation", False)):
                    ok = False
                    detail = f"{aid}.rules.allow_exclamation=true"
                    break
        elif kind == "reasonable_word_limits":
            max_allowed = int(params.get("max_allowed", 24))
            for aid in sorted(archetypes):
                rules = archetypes[aid].get("rules")
                max_words = int(rules.get("max_words", 0)) if isinstance(rules, dict) else 0
                if max_words <= 0 or max_words > max_allowed:
                    ok = False
                    detail = f"{aid}.rules.max_words={max_words}"
                    break

        checks.append(
            {
                "id": str(test.get("id") or ""),
                "kind": kind,
                "hard": hard,
                "weight": weight,
                "pass": ok,
                "detail": detail,
            }
        )

    hard_fail_count = sum(1 for row in checks if row["hard"] and not row["pass"])
    soft_total = sum(float(row["weight"]) for row in checks if not row["hard"])
    soft_earned = sum(float(row["weight"]) for row in checks if not row["hard"] and row["pass"])
    soft_score = (soft_earned / soft_total) if soft_total > 0 else 1.0
    overall_score = 0.0 if hard_fail_count > 0 else soft_score
    return {
        "hard_fail_count": hard_fail_count,
        "soft_score": round(soft_score, 6),
        "overall_score": round(overall_score, 6),
        "checks": checks,
    }


def _eval_meta_balance(blob: dict[str, Any], scenario_pack: dict[str, Any]) -> dict[str, Any]:
    archetypes = blob.get("archetypes") if isinstance(blob.get("archetypes"), dict) else {}
    balance = blob.get("balance") if isinstance(blob.get("balance"), dict) else {}
    arche_ids = sorted(archetypes.keys())
    dominant_threshold = float(balance.get("dominant_threshold", 0.55))
    first_player_advantage = float(balance.get("first_player_advantage", 0.0))
    aggregate: dict[str, float] = {}
    for left in arche_ids:
        row = archetypes[left].get("vs") if isinstance(archetypes[left], dict) else {}
        if not isinstance(row, dict):
            aggregate[left] = 0.0
            continue
        values = [float(row.get(right, 0.0)) for right in arche_ids]
        aggregate[left] = round(sum(values) / max(1, len(values)), 6)
    dominant = sorted([aid for aid, score in aggregate.items() if score >= dominant_threshold])

    checks: list[dict[str, Any]] = []
    for test in scenario_pack.get("tests", []):
        kind = str(test.get("kind") or "")
        params = test.get("params") if isinstance(test.get("params"), dict) else {}
        hard = bool(test.get("hard", False))
        weight = float(test.get("weight", 0.0))
        ok = True
        detail = ""

        if kind == "matrix_bounds":
            for left in arche_ids:
                row = archetypes[left].get("vs") if isinstance(archetypes[left], dict) else {}
                if not isinstance(row, dict):
                    ok = False
                    detail = f"{left}.vs missing"
                    break
                for right in arche_ids:
                    value = float(row.get(right, -1.0))
                    if value < 0.0 or value > 1.0:
                        ok = False
                        detail = f"{left}.vs.{right}={value}"
                        break
                if not ok:
                    break
        elif kind == "first_player_advantage_cap":
            max_allowed = float(params.get("max_allowed", 0.08))
            ok = first_player_advantage <= max_allowed
            if not ok:
                detail = f"first_player_advantage={first_player_advantage}"
        elif kind == "dominant_strategy_absent":
            ok = len(dominant) == 0
            if not ok:
                detail = ",".join(dominant)
        elif kind == "winrate_variance_cap":
            max_spread = float(params.get("max_spread", 0.15))
            if aggregate:
                spread = max(aggregate.values()) - min(aggregate.values())
            else:
                spread = 0.0
            ok = spread <= max_spread
            if not ok:
                detail = f"spread={round(spread, 6)}"

        checks.append(
            {
                "id": str(test.get("id") or ""),
                "kind": kind,
                "hard": hard,
                "weight": weight,
                "pass": ok,
                "detail": detail,
            }
        )

    hard_fail_count = sum(1 for row in checks if row["hard"] and not row["pass"])
    soft_total = sum(float(row["weight"]) for row in checks if not row["hard"])
    soft_earned = sum(float(row["weight"]) for row in checks if not row["hard"] and row["pass"])
    soft_score = (soft_earned / soft_total) if soft_total > 0 else 1.0
    overall_score = 0.0 if hard_fail_count > 0 else soft_score
    return {
        "hard_fail_count": hard_fail_count,
        "soft_score": round(soft_score, 6),
        "overall_score": round(overall_score, 6),
        "checks": checks,
    }


def _patch_templates(mode: str) -> list[list[dict[str, Any]]]:
    if mode == "truth_only":
        return [
            [
                {
                    "op": "replace",
                    "path": "/rules/defaults/allow_exclamation",
                    "value": False,
                }
            ],
            [
                {
                    "op": "replace",
                    "path": "/rules/defaults/max_words",
                    "value": 14,
                }
            ],
            [
                {
                    "op": "replace",
                    "path": "/banks/refusal_styles/REF_STYLE_STEEL/templates/0",
                    "value": "REFUSE\nrefusal_reason:restricted",
                }
            ],
        ]
    if mode == "meta_balance":
        return [
            [{"op": "replace", "path": "/balance/first_player_advantage", "value": 0.02}],
            [{"op": "replace", "path": "/balance/dominant_threshold", "value": 0.56}],
            [{"op": "replace", "path": "/archetypes/aggro/vs/control", "value": 0.54}],
        ]
    raise ValueError(f"unsupported mode: {mode}")


def _is_allowed_patch_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ALLOWED_PATCH_SURFACE)


def _path_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError(f"invalid patch path: {path}")
    return [part for part in path.split("/")[1:] if part != ""]


def _resolve_parent(container: Any, parts: list[str]) -> tuple[Any, str]:
    current = container
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError("invalid path resolution")
    return current, parts[-1]


def apply_patch_ops(blob: dict[str, Any], patch_ops: list[dict[str, Any]]) -> dict[str, Any]:
    output = copy.deepcopy(blob)
    for op in patch_ops:
        kind = str(op.get("op") or "")
        path = str(op.get("path") or "")
        if kind not in {"add", "remove", "replace", "move"}:
            raise ValueError(f"unsupported patch op: {kind}")
        if not _is_allowed_patch_path(path):
            raise ValueError(f"patch outside allowed surface: {path}")
        parts = _path_parts(path)
        parent, key = _resolve_parent(output, parts)
        if kind == "replace":
            if isinstance(parent, list):
                parent[int(key)] = op.get("value")
            else:
                parent[key] = op.get("value")
        elif kind == "add":
            if isinstance(parent, list):
                if key == "-":
                    parent.append(op.get("value"))
                else:
                    parent.insert(int(key), op.get("value"))
            else:
                parent[key] = op.get("value")
        elif kind == "remove":
            if isinstance(parent, list):
                del parent[int(key)]
            else:
                parent.pop(key, None)
        elif kind == "move":
            from_path = str(op.get("from") or "")
            if not _is_allowed_patch_path(from_path):
                raise ValueError(f"patch move from outside surface: {from_path}")
            src_parts = _path_parts(from_path)
            src_parent, src_key = _resolve_parent(output, src_parts)
            if isinstance(src_parent, list):
                value = src_parent.pop(int(src_key))
            else:
                value = src_parent.pop(src_key)
            if isinstance(parent, list):
                if key == "-":
                    parent.append(value)
                else:
                    parent.insert(int(key), value)
            else:
                parent[key] = value
    return output


def run_compile_pipeline(
    *,
    route_id: str,
    input_dir: Path,
    out_dir: Path,
    mode: str,
    model_id: str,
    seed: int,
    max_iters: int,
    scenario_pack_path: Path,
) -> CompilerRunResult:
    route = _resolve_route(route_id)
    plan = route.inspect(input_dir)

    artifacts = out_dir / "artifacts"
    materialized = out_dir / "materialized"
    candidates_dir = artifacts / "candidates"
    for path in (out_dir, artifacts, materialized, candidates_dir):
        path.mkdir(parents=True, exist_ok=True)

    route_plan_payload = {
        "route_id": plan.route_id,
        "expected_inputs": list(plan.expected_inputs),
        "found_inputs": list(plan.found_inputs),
        "missing_inputs": list(plan.missing_inputs),
        "errors": list(plan.errors),
        "warnings": list(plan.warnings),
    }
    (artifacts / "route_plan.json").write_text(json.dumps(route_plan_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not plan.ok:
        return CompilerRunResult(
            ok=False,
            hard_fail_count=1,
            best_score=0.0,
            best_candidate_id="none",
            artifact_root=artifacts,
            materialized_root=materialized,
        )

    canonical = route.normalize(input_dir)
    canonical_json = route.canonical_json(canonical)
    (artifacts / "canonical_blob.json").write_text(canonical_json + "\n", encoding="utf-8")

    inputs_manifest = _tree_manifest(input_dir)
    (artifacts / "inputs_manifest.json").write_text(json.dumps(inputs_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    scenario_pack = _load_scenario_pack(scenario_pack_path, mode=mode)
    (artifacts / "scenario_pack.json").write_text(json.dumps(scenario_pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    templates = _patch_templates(mode)

    candidates: list[dict[str, Any]] = []
    if mode == "truth_only":
        baseline_eval = _eval_truth_only(canonical, scenario_pack)
    elif mode == "meta_balance":
        baseline_eval = _eval_meta_balance(canonical, scenario_pack)
    else:
        raise ValueError(f"unsupported mode: {mode}")
    candidates.append(
        {
            "candidate_id": "0000",
            "patches": [],
            "blob_digest": _json_sha(canonical),
            "validation_ok": True,
            "score": baseline_eval["overall_score"],
            "hard_fail_count": baseline_eval["hard_fail_count"],
            "eval": baseline_eval,
        }
    )

    for i in range(1, max(1, int(max_iters)) + 1):
        idx = (int(seed) + i - 1) % len(templates)
        patch_ops = templates[idx]
        candidate_id = f"{i:04d}"
        candidate_payload: dict[str, Any] = {
            "candidate_id": candidate_id,
            "patches": patch_ops,
            "validation_ok": False,
            "score": -1_000_000_000.0,
            "hard_fail_count": 1_000_000,
        }
        try:
            mutated = apply_patch_ops(canonical, patch_ops)
            route.validate_blob(mutated)
            if mode == "truth_only":
                eval_result = _eval_truth_only(mutated, scenario_pack)
            else:
                eval_result = _eval_meta_balance(mutated, scenario_pack)
            candidate_payload.update(
                {
                    "validation_ok": True,
                    "blob_digest": _json_sha(mutated),
                    "score": float(eval_result["overall_score"]),
                    "hard_fail_count": int(eval_result["hard_fail_count"]),
                    "eval": eval_result,
                    "blob": mutated,
                }
            )
        except ValueError as exc:
            candidate_payload["error"] = str(exc)
        candidates.append(candidate_payload)

    for cand in candidates:
        file_path = candidates_dir / f"candidate_{cand['candidate_id']}.json"
        sanitized = {k: v for k, v in cand.items() if k != "blob"}
        file_path.write_text(json.dumps(sanitized, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ranked = sorted(
        candidates,
        key=lambda c: (
            int(c.get("hard_fail_count", 1_000_000)),
            -float(c.get("score", -1_000_000_000.0)),
            str(c.get("candidate_id", "")),
        ),
    )
    best = ranked[0]
    best_blob = best.get("blob", canonical) if isinstance(best.get("blob"), dict) else canonical

    route.materialize(best_blob, materialized)
    outputs_manifest = _tree_manifest(materialized)
    (artifacts / "outputs_manifest.json").write_text(json.dumps(outputs_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    final_score = {
        "mode": mode,
        "model_id": model_id,
        "seed": int(seed),
        "max_iters": int(max_iters),
        "best_candidate_id": best["candidate_id"],
        "best_score": float(best.get("score", 0.0)),
        "hard_fail_count": int(best.get("hard_fail_count", 0)),
        "baseline_candidate_id": "0000",
        "baseline_score": float(candidates[0]["score"]),
        "baseline_hard_fail_count": int(candidates[0]["hard_fail_count"]),
    }
    (artifacts / "final_score_report.json").write_text(json.dumps(final_score, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    outputs_payload = {
        "inputs_manifest_digest": _json_sha({"inputs": inputs_manifest}),
        "outputs_manifest_digest": _json_sha({"outputs": outputs_manifest}),
        "canonical_blob_digest": _json_sha(best_blob),
        "voice_profiles_digest": _json_sha(
            {"voice_profiles": best_blob.get("banks", {}).get("voice_profiles", {})}
        ),
        "route_id": route_id,
        "scenario_pack_id": scenario_pack["pack_id"],
        "scenario_pack_version": scenario_pack["version"],
    }
    (artifacts / "bundle_digests.json").write_text(json.dumps(outputs_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return CompilerRunResult(
        ok=int(best.get("hard_fail_count", 1)) == 0,
        hard_fail_count=int(best.get("hard_fail_count", 1)),
        best_score=float(best.get("score", 0.0)),
        best_candidate_id=str(best.get("candidate_id", "0000")),
        artifact_root=artifacts,
        materialized_root=materialized,
    )
