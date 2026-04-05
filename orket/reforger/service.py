from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.reforger.compiler import (
    _eval_meta_balance,
    _eval_truth_only,
    _json_sha,
    _load_scenario_pack,
    _resolve_route,
    _tree_manifest,
    run_compile_pipeline,
)
from orket.reforger.proof_slices import phase0_service_run_id, resolve_phase0_proof_slice
from orket.reforger.service_contracts import (
    BaselineMetrics,
    CandidateSummary,
    ExternalConsumerVerdict,
    PromptReforgerServiceRequest,
    PromptReforgerServiceResult,
    RESULT_CLASS_CERTIFIED,
    RESULT_CLASS_CERTIFIED_WITH_LIMITS,
    RESULT_CLASS_UNSUPPORTED,
    SERVICE_MODE_ADAPT,
)

_BRIDGE_ATTRIBUTION_KINDS = {"npc_archetype_exists", "npc_refusal_style_exists"}
_PROMPT_ATTRIBUTION_KINDS = {
    "no_exclamation_rules",
    "reasonable_word_limits",
    "refusal_templates_non_empty",
    "refusal_templates_use_reason_code",
}
_REQUALIFICATION_TRIGGERS = (
    "bridge_contract_change",
    "runtime_change",
    "validator_change",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _failure_records(*, checks: list[dict[str, Any]], eval_slice_ref: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in checks:
        if bool(row.get("pass", False)):
            continue
        kind = str(row.get("kind") or "")
        attribution = "prompt_behavior"
        if kind in _BRIDGE_ATTRIBUTION_KINDS:
            attribution = "bridge_behavior"
        elif kind not in _PROMPT_ATTRIBUTION_KINDS:
            attribution = "validator_behavior"
        records.append(
            {
                "error_code": None,
                "failure_label": kind or "unknown_failure",
                "source_authority_surface": eval_slice_ref,
                "attribution_class": attribution,
                "check_id": str(row.get("id") or ""),
                "detail": str(row.get("detail") or ""),
                "hard": bool(row.get("hard", False)),
            }
        )
    return records


def _classify_result(
    *,
    score: float,
    hard_fail_count: int,
    thresholds: PromptReforgerServiceRequest,
    winning_candidate_id: str | None,
) -> tuple[str, str]:
    if hard_fail_count == 0 and score >= thresholds.acceptance_thresholds.certified_min_score:
        if winning_candidate_id:
            return RESULT_CLASS_CERTIFIED, "winning candidate cleared certified_min_score"
        return RESULT_CLASS_CERTIFIED, "baseline cleared certified_min_score"
    if hard_fail_count == 0 and score >= thresholds.acceptance_thresholds.certified_with_limits_min_score:
        if winning_candidate_id:
            return (
                RESULT_CLASS_CERTIFIED_WITH_LIMITS,
                "winning candidate cleared certified_with_limits_min_score but did not clear certified_min_score",
            )
        return (
            RESULT_CLASS_CERTIFIED_WITH_LIMITS,
            "baseline cleared certified_with_limits_min_score but did not clear certified_min_score",
        )
    if winning_candidate_id:
        return (
            RESULT_CLASS_UNSUPPORTED,
            "winning candidate did not clear certified_with_limits_min_score",
        )
    return RESULT_CLASS_UNSUPPORTED, "baseline did not clear certified_with_limits_min_score"


def _service_run_id(request: PromptReforgerServiceRequest) -> str:
    proof_run_id = phase0_service_run_id(request.request_id)
    if proof_run_id:
        return proof_run_id
    return f"{request.artifact_token}-run"


def _load_materialized_outputs(root: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    materialized = root / "materialized"
    for item in sorted((p for p in materialized.rglob("*") if p.is_file()), key=lambda p: str(p)):
        rel = str(item.relative_to(materialized)).replace("\\", "/")
        outputs[rel] = item.read_text(encoding="utf-8")
    return outputs


def _scoreboard_payload(
    *,
    request: PromptReforgerServiceRequest,
    service_run_id: str,
    baseline_metrics: BaselineMetrics,
    candidate_records: list[dict[str, Any]],
    winning_candidate_id: str | None,
) -> dict[str, Any]:
    ranked = sorted(
        candidate_records,
        key=lambda row: (
            int(row["hard_fail_count"]),
            -float(row["score"]),
            str(row["candidate_id"]),
        ),
    )
    return {
        "schema_version": "prompt_reforger_service_scoreboard.v0",
        "request_id": request.request_id,
        "service_run_id": service_run_id,
        "service_mode": request.service_mode,
        "baseline_metrics": baseline_metrics.to_payload(),
        "ranked_candidates": ranked,
        "winning_candidate_id": winning_candidate_id,
    }


def _known_limits(result_class: str) -> tuple[str, ...]:
    if result_class == RESULT_CLASS_CERTIFIED_WITH_LIMITS:
        return (
            "narrowed acceptance envelope excludes exclamation-enabled persona variants",
            "fallback review is required when refusal-template authority drifts from the exercised bridge surface",
        )
    if result_class == RESULT_CLASS_UNSUPPORTED:
        return ("the exercised tuple did not clear the bounded acceptance thresholds",)
    return ()


@dataclass(frozen=True)
class PromptReforgerExecution:
    request: PromptReforgerServiceRequest
    result: PromptReforgerServiceResult
    run_artifact_path: Path
    scoreboard_artifact_path: Path
    run_artifact: dict[str, Any]
    scoreboard_artifact: dict[str, Any]

    def result_payload(self) -> dict[str, Any]:
        return self.result.to_payload()


class PromptReforgerService:
    def __init__(self, *, work_root: Path | None = None, artifact_root: Path | None = None) -> None:
        self.work_root = (work_root or (Path.cwd() / ".tmp" / "prompt_reforger_service")).resolve()
        self.artifact_root = (artifact_root or (Path.cwd() / "benchmarks" / "staging" / "General")).resolve()

    def execute_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.execute(PromptReforgerServiceRequest.from_payload(payload)).result_payload()

    def read_service_run(self, service_run_id: str) -> dict[str, Any]:
        return _read_json(self._run_artifact_path(service_run_id))

    def execute(self, request: PromptReforgerServiceRequest) -> PromptReforgerExecution:
        service_run_id = _service_run_id(request)
        run_artifact_path = self._run_artifact_path(service_run_id)
        scoreboard_artifact_path = self._scoreboard_artifact_path(service_run_id)
        work_dir = self.work_root / service_run_id
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        binding = resolve_phase0_proof_slice(
            bridge_contract_ref=request.bridge_contract_ref,
            eval_slice_ref=request.eval_slice_ref,
        )
        if binding is None:
            raise ValueError(
                "No bounded Phase 0 proof slice is registered for "
                f"{request.bridge_contract_ref} x {request.eval_slice_ref}"
            )
        materialized = binding.materialize(work_dir)
        input_dir = materialized["input_dir"]
        scenario_pack_path = materialized["scenario_pack_path"]
        bridge_contract_path = materialized["bridge_contract_path"]

        route = _resolve_route(binding.route_id)
        route_plan = route.inspect(input_dir)
        if not route_plan.ok:
            raise ValueError("Prompt Reforger proof slice materialized an invalid route plan")
        scenario_pack = _load_scenario_pack(scenario_pack_path, mode=binding.mode)

        baseline_metrics: BaselineMetrics
        winning_candidate_id: str | None = None
        winning_score: float | None = None
        candidate_records: list[dict[str, Any]] = []
        materialized_outputs: dict[str, str] = {}

        if request.service_mode == SERVICE_MODE_ADAPT:
            compile_root = work_dir / "compile"
            compile_result = run_compile_pipeline(
                route_id=binding.route_id,
                input_dir=input_dir,
                out_dir=compile_root,
                mode=binding.mode,
                model_id=request.runtime_context.model_id,
                seed=binding.candidate_seed,
                max_iters=int(request.candidate_budget or 0),
                scenario_pack_path=scenario_pack_path,
            )
            del compile_result
            final_score = _read_json(compile_root / "artifacts" / "final_score_report.json")
            baseline_candidate = _read_json(compile_root / "artifacts" / "candidates" / "candidate_0000.json")
            baseline_eval = baseline_candidate["eval"]
            baseline_metrics = BaselineMetrics(
                score=float(final_score["baseline_score"]),
                hard_fail_count=int(final_score["baseline_hard_fail_count"]),
                soft_fail_count=sum(1 for row in baseline_eval["checks"] if (not row["hard"]) and (not row["pass"])),
            )
            winning_candidate_id = str(final_score["best_candidate_id"])
            winning_score = float(final_score["best_score"])
            for path in sorted((compile_root / "artifacts" / "candidates").glob("candidate_*.json")):
                payload = _read_json(path)
                candidate_id = str(payload.get("candidate_id") or "")
                if candidate_id == "0000":
                    continue
                eval_payload = payload.get("eval") if isinstance(payload.get("eval"), dict) else {"checks": []}
                candidate_records.append(
                    {
                        "candidate_id": candidate_id,
                        "score": round(float(payload.get("score", 0.0)), 6),
                        "hard_fail_count": int(payload.get("hard_fail_count", 0)),
                        "validation_ok": bool(payload.get("validation_ok", False)),
                        "patches": list(payload.get("patches", [])),
                        "failure_records": _failure_records(
                            checks=list(eval_payload.get("checks", [])),
                            eval_slice_ref=request.eval_slice_ref,
                        ),
                    }
                )
            materialized_outputs = _load_materialized_outputs(compile_root)
            best_candidate = next(
                (
                    row
                    for row in [_read_json(path) for path in sorted((compile_root / "artifacts" / "candidates").glob("candidate_*.json"))]
                    if str(row.get("candidate_id") or "") == winning_candidate_id
                ),
                baseline_candidate,
            )
            best_eval = best_candidate["eval"]
        else:
            canonical = route.normalize(input_dir)
            if binding.mode == "truth_only":
                best_eval = _eval_truth_only(canonical, scenario_pack)
            else:
                best_eval = _eval_meta_balance(canonical, scenario_pack)
            baseline_metrics = BaselineMetrics(
                score=float(best_eval["overall_score"]),
                hard_fail_count=int(best_eval["hard_fail_count"]),
                soft_fail_count=sum(1 for row in best_eval["checks"] if (not row["hard"]) and (not row["pass"])),
            )

        result_class, acceptance_reason = _classify_result(
            score=float(best_eval["overall_score"]),
            hard_fail_count=int(best_eval["hard_fail_count"]),
            thresholds=request,
            winning_candidate_id=winning_candidate_id if winning_candidate_id != "0000" else None,
        )
        observed_result = "success" if result_class != RESULT_CLASS_UNSUPPORTED else "failure"
        bundle_ref = _path_text(run_artifact_path) if result_class != RESULT_CLASS_UNSUPPORTED else None
        candidate_summary = CandidateSummary(
            evaluated_candidate_count=len(candidate_records),
            winning_candidate_id=None if request.service_mode != SERVICE_MODE_ADAPT else winning_candidate_id,
            winning_score=None if request.service_mode != SERVICE_MODE_ADAPT else winning_score,
        )
        result = PromptReforgerServiceResult(
            request_id=request.request_id,
            service_run_id=service_run_id,
            result_class=result_class,
            observed_path="primary",
            observed_result=observed_result,
            runtime_context=request.runtime_context,
            bridge_contract_ref=request.bridge_contract_ref,
            eval_slice_ref=request.eval_slice_ref,
            baseline_metrics=baseline_metrics,
            candidate_summary=candidate_summary,
            acceptance_reason=acceptance_reason,
            bundle_ref=bundle_ref,
            known_limits=_known_limits(result_class),
            requalification_triggers=_REQUALIFICATION_TRIGGERS,
        )

        scoreboard_payload = _scoreboard_payload(
            request=request,
            service_run_id=service_run_id,
            baseline_metrics=baseline_metrics,
            candidate_records=candidate_records,
            winning_candidate_id=winning_candidate_id,
        )
        run_artifact = self._run_artifact_payload(
            request=request,
            result=result,
            route_plan=route_plan,
            bridge_contract_path=bridge_contract_path,
            scenario_pack_path=scenario_pack_path,
            input_dir=input_dir,
            candidate_records=candidate_records,
            materialized_outputs=materialized_outputs,
            scoreboard_artifact_path=scoreboard_artifact_path,
            live_proof_step=binding.live_proof_blocker_step,
            live_proof_error=binding.live_proof_blocker_error,
        )

        _write_json(run_artifact_path, run_artifact)
        _write_json(scoreboard_artifact_path, scoreboard_payload)
        return PromptReforgerExecution(
            request=request,
            result=result,
            run_artifact_path=run_artifact_path,
            scoreboard_artifact_path=scoreboard_artifact_path,
            run_artifact=run_artifact,
            scoreboard_artifact=scoreboard_payload,
        )

    def _run_artifact_path(self, service_run_id: str) -> Path:
        return self.artifact_root / f"reforger_service_run_{service_run_id}.json"

    def _scoreboard_artifact_path(self, service_run_id: str) -> Path:
        return self.artifact_root / f"reforger_service_run_{service_run_id}_scoreboard.json"

    def _run_artifact_payload(
        self,
        *,
        request: PromptReforgerServiceRequest,
        result: PromptReforgerServiceResult,
        route_plan: Any,
        bridge_contract_path: Path,
        scenario_pack_path: Path,
        input_dir: Path,
        candidate_records: list[dict[str, Any]],
        materialized_outputs: dict[str, str],
        scoreboard_artifact_path: Path,
        live_proof_step: str,
        live_proof_error: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "prompt_reforger_service_run.v0",
            "request": request.to_payload(),
            "result": result.to_payload(),
            "canonical_references": {
                "service_contract": "docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md",
                "bridge_contract_ref": request.bridge_contract_ref,
                "eval_slice_ref": request.eval_slice_ref,
                "route_id": getattr(route_plan, "route_id", ""),
                "bridge_contract_digest": _json_sha(_read_json(bridge_contract_path)),
                "scenario_pack_digest": _json_sha(_read_json(scenario_pack_path)),
                "input_manifest_digest": _json_sha({"inputs": _tree_manifest(input_dir)}),
            },
            "candidate_records": candidate_records,
            "scoreboard_ref": _path_text(scoreboard_artifact_path),
            "verification": {
                "proof_type": "structural",
                "live_proof": {
                    "observed_path": "blocked",
                    "observed_result": "environment blocker",
                    "failing_step": live_proof_step,
                    "error": live_proof_error,
                },
            },
            "truthfulness_assertions": {
                "provider_setting_tuning_performed": False,
                "canonical_schema_overridden": False,
                "canonical_validator_overridden": False,
                "consumer_orchestration_absorbed": False,
            },
        }
        if request.consumer_id:
            verdict = ExternalConsumerVerdict(
                consumer_id=request.consumer_id,
                verdict_class=result.result_class,
                verdict_source="service_adopted",
                service_result_ref=_path_text(self._run_artifact_path(result.service_run_id)),
            )
            payload["external_consumer_verdict"] = verdict.to_payload()
        if result.result_class != RESULT_CLASS_UNSUPPORTED:
            payload["qualifying_bundle"] = {
                "bundle_ref": _path_text(self._run_artifact_path(result.service_run_id)),
                "target_runtime_identity": request.runtime_context.to_payload(),
                "bridged_tool_surface_identity": request.bridge_contract_ref,
                "workload_eval_slice_identity": request.eval_slice_ref,
                "frozen_prompt_surfaces": materialized_outputs,
                "frozen_prompt_facing_tool_instructions": _read_json(bridge_contract_path)["tool_instructions"],
                "frozen_examples": _read_json(bridge_contract_path)["examples"],
                "frozen_prompt_facing_repair_retry_guidance": _read_json(bridge_contract_path)["repair_retry_guidance"],
                "canonical_tool_and_validator_refs": {
                    "bridge_contract_ref": request.bridge_contract_ref,
                    "eval_slice_ref": request.eval_slice_ref,
                },
                "scorecard_ref": _path_text(self._scoreboard_artifact_path(result.service_run_id)),
                "known_failure_boundaries": list(result.known_limits),
                "narrowed_acceptance_envelope": "No exclamation-enabled persona variants were accepted.",
                "fallback_review_requirements": "Re-run the bounded proof slice if refusal-template or bridge authority changes.",
                "runtime_condition_warning": (
                    "This bundle is scoped to the observed runtime context only and does not certify provider tuning."
                ),
                "consumer_boundary_warning": (
                    "This bundle does not claim consumer orchestration, bridge quality outside the exercised tuple, "
                    "or matrix-level authority."
                ),
                "requalification_triggers": list(result.requalification_triggers),
            }
        return payload
