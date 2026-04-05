from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.prompt_lab import guide_model_prompt_patch as guide_script
    from scripts.prompt_lab import run_prompt_reforger_gemma_tool_use_cycle as cycle_script
    from scripts.prompt_lab import score_prompt_reforger_gemma_tool_use_corpus as score_script
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    import guide_model_prompt_patch as guide_script
    import run_prompt_reforger_gemma_tool_use_cycle as cycle_script
    import score_prompt_reforger_gemma_tool_use_corpus as score_script


DEFAULT_OUTPUT = Path("benchmarks/staging/General/prompt_reforger_guide_model_comparison.json")
DEFAULT_WORK_ROOT = Path(".tmp/prompt_reforger_guide_model_comparison")
DEFAULT_INVENTORY = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json")
DEFAULT_CORPUS = Path("docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json")
IMPLEMENTATION_PLAN_REF = "docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md"


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Prompt Reforger guide models by generated prompt-candidate quality over the frozen Gemma tool-use corpus."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--work-root", default=str(DEFAULT_WORK_ROOT))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--targets", choices=["auto", "portability", "quality", "both"], default="portability")
    parser.add_argument("--guide-timeout-sec", type=int, default=60)
    parser.add_argument(
        "--guide-spec",
        action="append",
        default=[],
        help="Guide model spec: label|provider|model or label|provider|model|base_url",
    )
    return parser


def _default_baseline_candidate() -> dict[str, Any]:
    return {
        "candidate_id": "baseline",
        "label": "Baseline",
        "prompt_patch": "",
        "selection_kind": "baseline",
    }


def _score_candidate(
    *,
    repo_root: Path,
    corpus: dict[str, Any],
    challenge_row: dict[str, Any],
    candidate_root: Path,
) -> dict[str, Any]:
    run_summary_path = _resolve_repo_path(repo_root, str(challenge_row.get("run_summary_path") or ""))
    run_summary = _read_json(run_summary_path)
    observability_root = _resolve_repo_path(repo_root, f"{challenge_row['workspace']}/observability/{challenge_row['run_id']}")
    score_payload = score_script.score_corpus(
        corpus=corpus,
        run_summary=run_summary,
        observability_root=observability_root,
        repo_root=repo_root,
    )
    score_payload["source_run"]["run_summary_ref"] = _relativize(run_summary_path, repo_root)
    score_path = candidate_root / "score_report.json"
    write_payload_with_diff_ledger(score_path, score_payload)
    return score_payload


def _candidate_run(
    *,
    repo_root: Path,
    work_root: Path,
    corpus: dict[str, Any],
    target_row: dict[str, Any],
    candidate: dict[str, Any],
    runs: int,
) -> dict[str, Any]:
    target_role = str(target_row.get("role") or "").strip()
    candidate_root = work_root / target_role / str(candidate.get("candidate_id") or "")
    patch_path = cycle_script._candidate_patch_file(candidate, candidate_root)
    challenge_args = cycle_script._challenge_args(
        repo_root=repo_root,
        candidate_root=candidate_root,
        target_row=target_row,
        candidate=candidate,
        patch_path=patch_path,
        runs=runs,
    )
    challenge_payload = cycle_script._run_candidate_challenge(challenge_args)
    challenge_out = candidate_root / "challenge_report.json"
    write_payload_with_diff_ledger(challenge_out, challenge_payload)
    run_row = next((row for row in challenge_payload.get("runs") or [] if isinstance(row, dict)), None)
    if run_row is None or not str(run_row.get("run_summary_path") or "").strip():
        return {
            **cycle_script._candidate_envelope(candidate),
            "challenge_report_ref": _relativize(challenge_out, repo_root),
            "score_report_ref": "",
            "challenge_observed_result": str(challenge_payload.get("observed_result") or ""),
            "scoreboard": {},
            "blocking_error": "run_summary_missing",
        }
    score_payload = _score_candidate(
        repo_root=repo_root,
        corpus=corpus,
        challenge_row=run_row,
        candidate_root=candidate_root,
    )
    return {
        **cycle_script._candidate_envelope(candidate),
        "challenge_report_ref": _relativize(challenge_out, repo_root),
        "score_report_ref": _relativize(candidate_root / "score_report.json", repo_root),
        "challenge_observed_result": str(challenge_payload.get("observed_result") or ""),
        "scoreboard": dict(score_payload.get("scoreboard") or {}),
        "blocking_error": "",
    }


def _quality_summary(candidate_result: dict[str, Any], baseline_result: dict[str, Any]) -> dict[str, Any]:
    candidate_scoreboard = dict(candidate_result.get("scoreboard") or {})
    baseline_scoreboard = dict(baseline_result.get("scoreboard") or {})
    if not candidate_scoreboard or not baseline_scoreboard:
        return {
            "score_authority": "score_report.scoreboard",
            "comparison_ready": False,
            "baseline_available": bool(baseline_scoreboard),
            "improves_over_baseline": False,
            "accepted_delta_vs_baseline": 0,
            "partial_delta_vs_baseline": 0,
            "rejected_delta_vs_baseline": 0,
            "not_exercised_delta_vs_baseline": 0,
        }
    candidate_rank = cycle_script._candidate_rank_key(candidate_result)
    baseline_rank = cycle_script._candidate_rank_key(baseline_result)
    return {
        "score_authority": "score_report.scoreboard",
        "comparison_ready": True,
        "baseline_available": True,
        "improves_over_baseline": candidate_rank > baseline_rank,
        "accepted_slices": int(candidate_scoreboard.get("accepted_slices") or 0),
        "partial_slices": int(candidate_scoreboard.get("partial_slices") or 0),
        "rejected_slices": int(candidate_scoreboard.get("rejected_slices") or 0),
        "not_exercised_slices": int(candidate_scoreboard.get("not_exercised_slices") or 0),
        "accepted_delta_vs_baseline": int(candidate_scoreboard.get("accepted_slices") or 0)
        - int(baseline_scoreboard.get("accepted_slices") or 0),
        "partial_delta_vs_baseline": int(candidate_scoreboard.get("partial_slices") or 0)
        - int(baseline_scoreboard.get("partial_slices") or 0),
        "rejected_delta_vs_baseline": int(candidate_scoreboard.get("rejected_slices") or 0)
        - int(baseline_scoreboard.get("rejected_slices") or 0),
        "not_exercised_delta_vs_baseline": int(candidate_scoreboard.get("not_exercised_slices") or 0)
        - int(baseline_scoreboard.get("not_exercised_slices") or 0),
    }


def _guide_result_rank_key(result: dict[str, Any]) -> tuple[int, int, int, int, int]:
    quality = result.get("candidate_generation_quality") if isinstance(result.get("candidate_generation_quality"), dict) else {}
    return (
        1 if bool(quality.get("improves_over_baseline")) else 0,
        int(quality.get("accepted_delta_vs_baseline") or 0),
        int(quality.get("partial_delta_vs_baseline") or 0),
        -int(quality.get("rejected_slices") or 0),
        -int(quality.get("not_exercised_slices") or 0),
    )


def _target_comparison(
    *,
    repo_root: Path,
    work_root: Path,
    corpus: dict[str, Any],
    corpus_ref: str,
    target_row: dict[str, Any],
    guide_specs: list[guide_script.GuideModelSpec],
    runs: int,
    guide_timeout_sec: int,
) -> dict[str, Any]:
    runtime_target = target_row.get("runtime_target") if isinstance(target_row.get("runtime_target"), dict) else {}
    target_role = str(target_row.get("role") or "").strip()
    target_model = str(runtime_target.get("requested_model") or target_row.get("requested_model") or "")
    if str(runtime_target.get("status") or "").strip().upper() != "OK":
        return {
            "target_role": target_role,
            "requested_provider": str(target_row.get("requested_provider") or ""),
            "requested_model": target_model,
            "observed_path": "blocked",
            "observed_result": "environment blocker",
            "blocking_error": str(target_row.get("blocking_error") or "target_not_available"),
            "baseline_result": {},
            "guide_results": [],
            "winning_guide_label": "",
        }

    baseline_result = _candidate_run(
        repo_root=repo_root,
        work_root=work_root,
        corpus=corpus,
        target_row=target_row,
        candidate=_default_baseline_candidate(),
        runs=int(runs),
    )
    baseline_ready = bool((baseline_result.get("scoreboard") or {}))
    guide_results: list[dict[str, Any]] = []
    for guide_spec in guide_specs:
        guide_root = work_root / target_role / f"guide_{guide_spec.label}"
        generation_path = guide_root / "guide_generation.json"
        generation_payload = guide_script.generate_guide_candidate(
            repo_root=repo_root,
            corpus=corpus,
            corpus_ref=corpus_ref,
            target_role=target_role,
            target_model=target_model,
            guide_spec=guide_spec,
            out_path=generation_path,
            timeout_sec=int(guide_timeout_sec),
        )
        generated_candidate = (
            dict(generation_payload.get("generated_candidate") or {})
            if isinstance(generation_payload.get("generated_candidate"), dict)
            else {}
        )
        candidate_result: dict[str, Any]
        if generated_candidate and str(generated_candidate.get("prompt_patch") or "").strip():
            if baseline_ready:
                candidate_result = _candidate_run(
                    repo_root=repo_root,
                    work_root=work_root,
                    corpus=corpus,
                    target_row=target_row,
                    candidate=generated_candidate,
                    runs=int(runs),
                )
            else:
                candidate_result = {
                    "candidate_id": str(generated_candidate.get("candidate_id") or f"guide_{guide_spec.label}"),
                    "candidate_label": str(generated_candidate.get("label") or guide_spec.label),
                    "selection_kind": "guide_model",
                    "prompt_patch": str(generated_candidate.get("prompt_patch") or ""),
                    "prompt_patch_checksum": str(generated_candidate.get("prompt_patch_checksum") or ""),
                    "challenge_report_ref": "",
                    "score_report_ref": "",
                    "challenge_observed_result": "",
                    "scoreboard": {},
                    "blocking_error": str(
                        baseline_result.get("blocking_error") or "baseline_scoreboard_missing_for_comparison"
                    ),
                }
        else:
            candidate_result = {
                "candidate_id": str(generated_candidate.get("candidate_id") or f"guide_{guide_spec.label}"),
                "candidate_label": str(generated_candidate.get("label") or guide_spec.label),
                "selection_kind": "guide_model",
                "prompt_patch": str(generated_candidate.get("prompt_patch") or ""),
                "prompt_patch_checksum": str(generated_candidate.get("prompt_patch_checksum") or ""),
                "challenge_report_ref": "",
                "score_report_ref": "",
                "challenge_observed_result": "",
                "scoreboard": {},
                "blocking_error": str(generation_payload.get("blocking_error") or "guide_candidate_generation_failed"),
            }
        guide_results.append(
            {
                "guide_label": guide_spec.label,
                "guide_provider": guide_spec.provider,
                "guide_model": guide_spec.model,
                "guide_generation_ref": _relativize(generation_path, repo_root),
                "guide_generation_observed_path": str(generation_payload.get("observed_path") or ""),
                "guide_generation_observed_result": str(generation_payload.get("observed_result") or ""),
                "guide_generation_blocking_error": str(generation_payload.get("blocking_error") or ""),
                "generated_candidate": generated_candidate,
                "candidate_result": candidate_result,
                "candidate_generation_quality": _quality_summary(candidate_result, baseline_result),
            }
        )
    ranked = sorted(guide_results, key=_guide_result_rank_key, reverse=True)
    winner = ranked[0] if ranked and baseline_ready else {}
    return {
        "target_role": target_role,
        "requested_provider": str(target_row.get("requested_provider") or ""),
        "requested_model": target_model,
        "observed_path": "primary" if baseline_ready else "degraded",
        "observed_result": "success" if baseline_ready else "environment blocker",
        "blocking_error": "" if baseline_ready else str(baseline_result.get("blocking_error") or "baseline_scoreboard_missing"),
        "baseline_result": baseline_result,
        "guide_results": guide_results,
        "winning_guide_label": str(winner.get("guide_label") or ""),
    }


def run_comparison(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(str(args.repo_root)).resolve()
    inventory_path = _resolve_repo_path(repo_root, str(args.inventory))
    corpus_path = _resolve_repo_path(repo_root, str(args.corpus))
    work_root = _resolve_repo_path(repo_root, str(args.work_root))
    work_root.mkdir(parents=True, exist_ok=True)
    inventory = cycle_script._ensure_inventory(repo_root, inventory_path)
    corpus = _read_json(corpus_path)
    if not isinstance(corpus, dict):
        raise ValueError("corpus must be a JSON object")
    guide_specs = [guide_script.GuideModelSpec.parse(raw) for raw in list(args.guide_spec or [])]
    if not guide_specs:
        raise ValueError("At least one --guide-spec is required.")
    rows = cycle_script._inventory_rows_by_role(inventory)
    target_results = [
        _target_comparison(
            repo_root=repo_root,
            work_root=work_root,
            corpus=corpus,
            corpus_ref=_relativize(corpus_path, repo_root),
            target_row=rows.get(target_role) or {},
            guide_specs=guide_specs,
            runs=int(args.runs),
            guide_timeout_sec=int(args.guide_timeout_sec),
        )
        for target_role in cycle_script._target_roles(inventory, str(args.targets))
    ]
    blocked_targets = [row for row in target_results if str(row.get("observed_path") or "") in {"blocked", "degraded"}]
    guide_rows = [
        row
        for target in target_results
        for row in (target.get("guide_results") or [])
        if isinstance(row, dict)
    ]
    improved_rows = [
        row
        for row in guide_rows
        if bool(((row.get("candidate_generation_quality") or {}).get("improves_over_baseline")))
    ]
    comparison_ready_rows = [
        row
        for row in guide_rows
        if bool(((row.get("candidate_generation_quality") or {}).get("comparison_ready")))
    ]
    blocked_guides = [
        row
        for row in guide_rows
        if str(row.get("guide_generation_observed_path") or "") == "blocked"
    ]
    observed_path = "primary" if not blocked_targets else "degraded"
    if not comparison_ready_rows:
        observed_result = "environment blocker"
    elif target_results and len(improved_rows) > 0:
        observed_result = "success"
    elif target_results:
        observed_result = "partial success"
    else:
        observed_result = "environment blocker"
    return {
        "schema_version": "prompt_reforger_guide_model_comparison.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "observed_path": observed_path if guide_rows else "blocked",
        "observed_result": observed_result if guide_rows else "environment blocker",
        "implementation_plan_ref": IMPLEMENTATION_PLAN_REF,
        "inventory_ref": _relativize(inventory_path, repo_root),
        "corpus_ref": _relativize(corpus_path, repo_root),
        "guide_models": [spec.to_payload() for spec in guide_specs],
        "comparison_basis": "candidate_generation_quality",
        "target_results": target_results,
        "summary": {
            "guide_models_total": len(guide_specs),
            "targets_total": len(target_results),
            "comparison_ready_runs": len(comparison_ready_rows),
            "improved_guide_runs": len(improved_rows),
            "blocked_guide_runs": len(blocked_guides),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    out_path = _resolve_repo_path(repo_root, str(args.out))
    payload = run_comparison(args)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "observed_path": str(payload.get("observed_path") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "guide_models_total": int((payload.get("summary") or {}).get("guide_models_total") or 0),
                "improved_guide_runs": int((payload.get("summary") or {}).get("improved_guide_runs") or 0),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0 if str(payload.get("observed_result") or "") != "environment blocker" else 1


if __name__ == "__main__":
    raise SystemExit(main())
