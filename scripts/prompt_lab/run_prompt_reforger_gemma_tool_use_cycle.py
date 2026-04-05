from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.benchmarks import run_local_model_coding_challenge as challenge_script
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.prompt_lab import run_functiongemma_tool_call_judge as judge_script
    from scripts.prompt_lab import run_prompt_reforger_gemma_tool_use_inventory as inventory_script
    from scripts.prompt_lab import score_prompt_reforger_gemma_tool_use_corpus as score_script
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks import run_local_model_coding_challenge as challenge_script
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    import run_functiongemma_tool_call_judge as judge_script
    import run_prompt_reforger_gemma_tool_use_inventory as inventory_script
    import score_prompt_reforger_gemma_tool_use_corpus as score_script


DEFAULT_OUTPUT = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_cycle.json")
DEFAULT_WORK_ROOT = Path(".tmp/prompt_reforger_gemma_tool_use_cycle")
DEFAULT_INVENTORY = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json")
DEFAULT_CORPUS = Path("docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json")
IMPLEMENTATION_PLAN_REF = "docs/projects/PromptReforgerToolCompatibility/PROMPT_REFORGER_GEMMA_TOOL_USE_IMPLEMENTATION_PLAN.md"

_CANDIDATES = (
    {
        "candidate_id": "baseline",
        "label": "Baseline",
        "prompt_patch": "",
        "selection_kind": "baseline",
    },
    {
        "candidate_id": "multi_write_completion_v1",
        "label": "Multi-write completion",
        "prompt_patch": (
            "MULTI-WRITE REINFORCEMENT:\n"
            "- When a turn lists multiple required write paths, emit one write_file call for every listed path "
            "in the same response before update_issue_status.\n"
            "- Do not stop after writing only the primary output path.\n"
            "- Treat any omitted required write path as a failed turn."
        ),
        "selection_kind": "candidate",
    },
    {
        "candidate_id": "workflow_fixture_shape_v1",
        "label": "Workflow fixture shape",
        "prompt_patch": (
            "FIXTURE SHAPE REMINDER:\n"
            "- challenge_inputs JSON fixtures must keep root keys workflow_id, max_concurrency, tasks.\n"
            "- task objects must keep only id, deps, duration, retries, outcomes.\n"
            "- For the valid fixture: task1 has deps []; task2 and task3 each depend on task1; task4 depends on both "
            "task2 and task3.\n"
            "- For the cycle fixture: only task1 and task2 exist and depend on each other.\n"
            "- For the retry fixture: only task1 exists with retries 1 and outcomes ['failure', 'success']."
        ),
        "selection_kind": "candidate",
    },
)


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
        description="Run the bounded Gemma tool-use prompt reforge cycle over the frozen challenge_workflow_runtime corpus."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--work-root", default=str(DEFAULT_WORK_ROOT))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--targets", choices=["auto", "portability", "quality", "both"], default="auto")
    parser.add_argument("--judge-timeout-sec", type=int, default=60)
    return parser


@contextmanager
def _patched_env(**values: str):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _ensure_inventory(repo_root: Path, inventory_path: Path) -> dict[str, Any]:
    if inventory_path.exists():
        payload = _read_json(inventory_path)
        if isinstance(payload, dict):
            return payload
    args = SimpleNamespace(
        repo_root=str(repo_root),
        out=str(inventory_path),
        timeout_sec=inventory_script.DEFAULT_TIMEOUT_S,
        model_load_timeout_sec=inventory_script.DEFAULT_MODEL_LOAD_TIMEOUT_S,
        model_ttl_sec=inventory_script.DEFAULT_MODEL_TTL_SEC,
        auto_load_local_model=True,
    )
    payload = inventory_script.run_inventory(args)
    write_payload_with_diff_ledger(inventory_path, payload)
    return payload


def _inventory_rows_by_role(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("inventory_targets") if isinstance(payload.get("inventory_targets"), list) else []
    return {
        str(row.get("role") or ""): row
        for row in rows
        if isinstance(row, dict) and str(row.get("role") or "").strip()
    }


def _target_roles(inventory: dict[str, Any], selection: str) -> list[str]:
    rows = _inventory_rows_by_role(inventory)
    portability_ok = str((rows.get("proposer_portability") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    quality_ok = str((rows.get("proposer_quality") or {}).get("runtime_target", {}).get("status") or "") == "OK"
    if selection == "portability":
        return ["proposer_portability"]
    if selection == "quality":
        return ["proposer_quality"]
    if selection == "both":
        return ["proposer_portability", "proposer_quality"]
    if quality_ok:
        return ["proposer_portability", "proposer_quality"]
    if portability_ok:
        return ["proposer_portability"]
    return ["proposer_portability", "proposer_quality"]


def _candidate_rank_key(candidate: dict[str, Any]) -> tuple[int, int, int, int, int]:
    scoreboard = candidate.get("scoreboard") if isinstance(candidate.get("scoreboard"), dict) else {}
    return (
        int(scoreboard.get("accepted_slices") or 0),
        int(scoreboard.get("partial_slices") or 0),
        -int(scoreboard.get("rejected_slices") or 0),
        -int(scoreboard.get("not_exercised_slices") or 0),
        1 if str(candidate.get("candidate_id") or "") == "baseline" else 0,
    )


def _promotion_decision(target_results: list[dict[str, Any]]) -> dict[str, Any]:
    portability = next((row for row in target_results if row.get("target_role") == "proposer_portability"), None)
    quality = next((row for row in target_results if row.get("target_role") == "proposer_quality"), None)
    portability_scoreboard = portability.get("best_scoreboard") if isinstance((portability or {}).get("best_scoreboard"), dict) else {}
    quality_scoreboard = quality.get("best_scoreboard") if isinstance((quality or {}).get("best_scoreboard"), dict) else {}
    portability_full = int(portability_scoreboard.get("accepted_slices") or 0) == int(
        portability_scoreboard.get("slices_total") or 0
    )
    quality_full = bool(quality_scoreboard) and int(quality_scoreboard.get("accepted_slices") or 0) == int(
        quality_scoreboard.get("slices_total") or 0
    )
    if portability_full and (not quality or quality_full):
        return {
            "decision": "keep_all_gemma_primary",
            "cross_family_baseline_needed": False,
            "reason": "The bounded portability path cleared the frozen corpus and no cross-family baseline is required yet.",
        }
    return {
        "decision": "pause_lane_with_blockers",
        "cross_family_baseline_needed": False,
        "reason": (
            "The bounded Gemma-only lane did not clear the frozen portability corpus, so the truthful decision is to "
            "pause promotion and keep the blockers explicit."
        ),
    }


def _candidate_patch_file(candidate: dict[str, Any], root: Path) -> Path | None:
    prompt_patch = str(candidate.get("prompt_patch") or "")
    if not prompt_patch:
        return None
    patch_path = root / "prompt_patch.txt"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(prompt_patch + "\n", encoding="utf-8")
    return patch_path


def _prompt_patch_checksum(candidate: dict[str, Any]) -> str:
    prompt_patch = str(candidate.get("prompt_patch") or "")
    if not prompt_patch:
        return ""
    return hashlib.sha256(prompt_patch.encode("utf-8")).hexdigest()[:16]


def _candidate_envelope(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_label": candidate["label"],
        "selection_kind": candidate["selection_kind"],
        "prompt_patch": str(candidate.get("prompt_patch") or ""),
        "prompt_patch_checksum": _prompt_patch_checksum(candidate),
    }


def _challenge_args(
    *,
    repo_root: Path,
    candidate_root: Path,
    target_row: dict[str, Any],
    candidate: dict[str, Any],
    patch_path: Path | None,
    runs: int,
) -> argparse.Namespace:
    runtime_target = target_row.get("runtime_target") if isinstance(target_row.get("runtime_target"), dict) else {}
    return argparse.Namespace(
        repo_root=str(repo_root),
        out=str(candidate_root / "challenge_report.json"),
        epic="challenge_workflow_runtime",
        provider=str(target_row.get("requested_provider") or ""),
        model=str(runtime_target.get("requested_model") or target_row.get("requested_model") or ""),
        runs=int(runs),
        workspace_root=str(candidate_root / "workspace"),
        build_id_prefix=f"{target_row['role']}_{candidate['candidate_id']}",
        python_bin=sys.executable,
        prompt_patch_file=(str(patch_path) if patch_path is not None else ""),
        prompt_patch_label=str(candidate.get("candidate_id") or ""),
    )


def _run_candidate_challenge(challenge_args: argparse.Namespace) -> dict[str, Any]:
    with _patched_env(ORKET_PROMPT_RESOLVER_MODE="resolver", ORKET_PROMPT_SELECTION_POLICY="stable"):
        return challenge_script.run_local_model_coding_challenge(challenge_args)


def _score_and_judge_candidate(
    *,
    repo_root: Path,
    corpus: dict[str, Any],
    inventory: dict[str, Any],
    challenge_row: dict[str, Any],
    candidate_root: Path,
    judge_timeout_sec: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_summary_path = _resolve_repo_path(repo_root, str(challenge_row.get("run_summary_path") or ""))
    run_summary = _read_json(run_summary_path)
    observability_root = _resolve_repo_path(
        repo_root,
        f"{challenge_row['workspace']}/observability/{challenge_row['run_id']}",
    )
    score_payload = score_script.score_corpus(
        corpus=corpus,
        run_summary=run_summary,
        observability_root=observability_root,
        repo_root=repo_root,
    )
    score_payload["source_run"]["run_summary_ref"] = _relativize(run_summary_path, repo_root)
    write_payload_with_diff_ledger(candidate_root / "score_report.json", score_payload)
    judge_payload = judge_script.run_judge(
        repo_root=repo_root,
        score_report=score_payload,
        inventory=inventory,
        timeout_sec=judge_timeout_sec,
    )
    judge_payload["score_report_ref"] = _relativize(candidate_root / "score_report.json", repo_root)
    write_payload_with_diff_ledger(candidate_root / "judge_report.json", judge_payload)
    return score_payload, judge_payload


def _candidate_run(
    *,
    repo_root: Path,
    work_root: Path,
    corpus: dict[str, Any],
    inventory: dict[str, Any],
    target_row: dict[str, Any],
    candidate: dict[str, Any],
    runs: int,
    judge_timeout_sec: int,
) -> dict[str, Any]:
    target_role = str(target_row.get("role") or "").strip()
    candidate_root = work_root / target_role / str(candidate.get("candidate_id") or "")
    patch_path = _candidate_patch_file(candidate, candidate_root)
    challenge_args = _challenge_args(
        repo_root=repo_root,
        candidate_root=candidate_root,
        target_row=target_row,
        candidate=candidate,
        patch_path=patch_path,
        runs=runs,
    )
    challenge_payload = _run_candidate_challenge(challenge_args)
    challenge_out = candidate_root / "challenge_report.json"
    write_payload_with_diff_ledger(challenge_out, challenge_payload)
    run_row = next((row for row in challenge_payload.get("runs") or [] if isinstance(row, dict)), None)
    if run_row is None or not str(run_row.get("run_summary_path") or "").strip():
        return {
            **_candidate_envelope(candidate),
            "challenge_report_ref": _relativize(challenge_out, repo_root),
            "score_report_ref": "",
            "judge_report_ref": "",
            "challenge_observed_result": str(challenge_payload.get("observed_result") or ""),
            "scoreboard": {},
            "judge_summary": {},
            "blocking_error": "run_summary_missing",
        }
    score_payload, judge_payload = _score_and_judge_candidate(
        repo_root=repo_root,
        corpus=corpus,
        inventory=inventory,
        challenge_row=run_row,
        candidate_root=candidate_root,
        judge_timeout_sec=judge_timeout_sec,
    )
    return {
        **_candidate_envelope(candidate),
        "challenge_report_ref": _relativize(challenge_out, repo_root),
        "score_report_ref": _relativize(candidate_root / "score_report.json", repo_root),
        "judge_report_ref": _relativize(candidate_root / "judge_report.json", repo_root),
        "challenge_observed_result": str(challenge_payload.get("observed_result") or ""),
        "scoreboard": dict(score_payload.get("scoreboard") or {}),
        "judge_summary": dict(judge_payload.get("summary") or {}),
        "judge_observed_path": str(judge_payload.get("observed_path") or ""),
        "judge_observed_result": str(judge_payload.get("observed_result") or ""),
        "blocking_error": "",
    }


def run_cycle(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(str(args.repo_root)).resolve()
    inventory_path = _resolve_repo_path(repo_root, str(args.inventory))
    corpus_path = _resolve_repo_path(repo_root, str(args.corpus))
    work_root = _resolve_repo_path(repo_root, str(args.work_root))
    work_root.mkdir(parents=True, exist_ok=True)
    inventory = _ensure_inventory(repo_root, inventory_path)
    corpus = _read_json(corpus_path)
    if not isinstance(corpus, dict):
        raise ValueError("corpus must be a JSON object")
    rows = _inventory_rows_by_role(inventory)
    target_results: list[dict[str, Any]] = []
    for target_role in _target_roles(inventory, str(args.targets)):
        target_row = rows.get(target_role) or {}
        runtime_target = target_row.get("runtime_target") if isinstance(target_row.get("runtime_target"), dict) else {}
        if str(runtime_target.get("status") or "").strip().upper() != "OK":
            target_results.append(
                {
                    "target_role": target_role,
                    "requested_provider": str(target_row.get("requested_provider") or ""),
                    "requested_model": str(target_row.get("requested_model") or ""),
                    "observed_path": "blocked",
                    "observed_result": "environment blocker",
                    "blocking_error": str(target_row.get("blocking_error") or "target_not_available"),
                    "candidate_results": [],
                    "winning_candidate_id": "",
                    "best_scoreboard": {},
                }
            )
            continue
        candidate_results = [
            _candidate_run(
                repo_root=repo_root,
                work_root=work_root,
                corpus=corpus,
                inventory=inventory,
                target_row=target_row,
                candidate=candidate,
                runs=int(args.runs),
                judge_timeout_sec=int(args.judge_timeout_sec),
            )
            for candidate in _CANDIDATES
        ]
        ranked = sorted(candidate_results, key=_candidate_rank_key, reverse=True)
        winner = ranked[0] if ranked else {}
        target_results.append(
            {
                "target_role": target_role,
                "requested_provider": str(target_row.get("requested_provider") or ""),
                "requested_model": str(runtime_target.get("requested_model") or target_row.get("requested_model") or ""),
                "observed_path": "primary",
                "observed_result": "success" if ranked else "partial success",
                "blocking_error": "",
                "winning_candidate_id": str(winner.get("candidate_id") or ""),
                "baseline_candidate_id": "baseline",
                "best_scoreboard": dict(winner.get("scoreboard") or {}),
                "candidate_results": candidate_results,
            }
        )
    promotion = _promotion_decision(target_results)
    blocked_targets = [row for row in target_results if str(row.get("observed_path") or "") == "blocked"]
    observed_path = "primary" if not blocked_targets else "degraded"
    observed_result = "success" if promotion["decision"] == "keep_all_gemma_primary" else "partial success"
    return {
        "schema_version": "prompt_reforger_gemma_tool_use_cycle.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "implementation_plan_ref": IMPLEMENTATION_PLAN_REF,
        "inventory_ref": _relativize(inventory_path, repo_root),
        "corpus_ref": _relativize(corpus_path, repo_root),
        "candidate_set": list(_CANDIDATES),
        "target_results": target_results,
        "promotion_decision": promotion,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    out_path = _resolve_repo_path(repo_root, str(args.out))
    payload = run_cycle(args)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "observed_path": str(payload.get("observed_path") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "promotion_decision": str((payload.get("promotion_decision") or {}).get("decision") or ""),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
