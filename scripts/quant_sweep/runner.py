from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from providers.lmstudio_model_cache import LmStudioCacheClearError
from quant_sweep.canary import run_canary
from quant_sweep.config import (
    apply_matrix_config,
    model_cache_sanitation_plan,
    parse_args,
    resolve_runtime_env,
    resolve_sidecar_settings,
    sanitize_model_cache,
)
from quant_sweep.runtime import git_commit_sha
from quant_sweep.workflow import (
    build_dry_plan,
    build_quant_row,
    build_session,
    build_summary,
    resolve_models_and_quants,
    run_quant_harness,
)


def _prepare_context(
    args: argparse.Namespace,
) -> tuple[dict[str, str], dict[str, Any], str, int, str, list[str], list[str], Path, Path, str]:
    runtime_env = resolve_runtime_env(getattr(args, "runtime_env", {}))
    cache_plan = model_cache_sanitation_plan(args, runtime_env)
    sidecar_template, sidecar_timeout_sec, sidecar_profile = resolve_sidecar_settings(args)
    model_ids, quant_tags = resolve_models_and_quants(args)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = Path(args.summary_out)
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    commit_sha = git_commit_sha()
    return (
        runtime_env,
        cache_plan,
        sidecar_template,
        sidecar_timeout_sec,
        sidecar_profile,
        model_ids,
        quant_tags,
        out_dir,
        summary_out,
        git_commit_sha(),
    )


def _run_sessions(
    *,
    args: argparse.Namespace,
    model_ids: list[str],
    quant_tags: list[str],
    runtime_env: dict[str, str],
    sidecar_template: str,
    sidecar_timeout_sec: int,
    out_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    canary_result = None
    if int(args.canary_runs) > 0:
        canary_result = run_canary(
            args=args,
            model_id=model_ids[0],
            quant_tag=quant_tags[0],
            out_dir=out_dir,
            runtime_env=runtime_env,
        )
        if not bool(canary_result.get("passed")):
            print(json.dumps({"canary": canary_result}, indent=2))
            raise SystemExit("Canary gate failed; aborting quant sweep.")
    sessions: list[dict[str, Any]] = []
    from quant_sweep.sidecar import quant_report_out

    for model_id in model_ids:
        per_quant: list[dict[str, Any]] = []
        for quant_tag in quant_tags:
            report_path = quant_report_out(out_dir, model_id, quant_tag)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            run_quant_harness(args=args, model_id=model_id, quant_tag=quant_tag, runtime_env=runtime_env, out_path=report_path)
            per_quant.append(
                build_quant_row(
                    args=args,
                    model_id=model_id,
                    quant_tag=quant_tag,
                    report_path=report_path,
                    sidecar_template=sidecar_template,
                    sidecar_timeout_sec=sidecar_timeout_sec,
                    out_dir=out_dir,
                )
            )
        if per_quant:
            sessions.append(build_session(args=args, model_id=model_id, per_quant=per_quant))
    if not sessions:
        raise SystemExit("No quant runs collected")
    return sessions, canary_result


def _run_with_sanitation(
    *,
    args: argparse.Namespace,
    cache_plan: dict[str, Any],
    model_ids: list[str],
    quant_tags: list[str],
    runtime_env: dict[str, str],
    sidecar_template: str,
    sidecar_timeout_sec: int,
    out_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[dict[str, Any]]]:
    sanitation_events: list[dict[str, Any]] = []
    try:
        sanitation_events.append(sanitize_model_cache("pre_run", cache_plan))
    except LmStudioCacheClearError as exc:
        raise SystemExit(str(exc)) from exc
    sweep_error: SystemExit | None = None
    sessions: list[dict[str, Any]] = []
    canary_result = None
    try:
        sessions, canary_result = _run_sessions(
            args=args,
            model_ids=model_ids,
            quant_tags=quant_tags,
            runtime_env=runtime_env,
            sidecar_template=sidecar_template,
            sidecar_timeout_sec=sidecar_timeout_sec,
            out_dir=out_dir,
        )
    except SystemExit as exc:
        sweep_error = exc
    finally:
        try:
            sanitation_events.append(sanitize_model_cache("post_run", cache_plan))
        except LmStudioCacheClearError as exc:
            if sweep_error is None:
                sweep_error = SystemExit(str(exc))
            else:
                print(str(exc))
    if sweep_error is not None:
        raise sweep_error
    return sessions, canary_result, sanitation_events


def run_quant_sweep() -> int:
    args = apply_matrix_config(parse_args())
    (
        runtime_env,
        cache_plan,
        sidecar_template,
        sidecar_timeout_sec,
        sidecar_profile,
        model_ids,
        quant_tags,
        out_dir,
        summary_out,
        commit_sha,
    ) = _prepare_context(args)
    if args.dry_run:
        dry_plan = build_dry_plan(
            args=args,
            commit_sha=commit_sha,
            model_ids=model_ids,
            quant_tags=quant_tags,
            runtime_env=runtime_env,
            cache_plan=cache_plan,
            sidecar_template=sidecar_template,
            sidecar_timeout_sec=sidecar_timeout_sec,
            sidecar_profile=sidecar_profile,
            out_dir=out_dir,
            summary_out=summary_out,
        )
        print(json.dumps({"dry_run": dry_plan}, indent=2))
        return 0
    sessions, canary_result, sanitation_events = _run_with_sanitation(
        args=args,
        cache_plan=cache_plan,
        model_ids=model_ids,
        quant_tags=quant_tags,
        runtime_env=runtime_env,
        sidecar_template=sidecar_template,
        sidecar_timeout_sec=sidecar_timeout_sec,
        out_dir=out_dir,
    )
    summary = build_summary(
        args=args,
        commit_sha=commit_sha,
        model_ids=model_ids,
        quant_tags=quant_tags,
        sidecar_template=sidecar_template,
        sidecar_profile=sidecar_profile,
        sidecar_timeout_sec=sidecar_timeout_sec,
        runtime_env=runtime_env,
        cache_plan=cache_plan,
        sanitation_events=sanitation_events,
        canary_result=canary_result,
        sessions=sessions,
    )
    summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0
