from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from orket.application.review.bundle_validation import ReviewBundleError, load_review_replay_artifacts
from orket.application.review.models import ReviewSnapshot, SnapshotBounds
from orket.application.review.run_service import ReviewRunService
from orket.interfaces.bundle_cli_output import emit_result

ERROR_REVIEW_ARGUMENTS = "E_REVIEW_ARGUMENTS"
ERROR_REVIEW_RUN_FAILED = "E_REVIEW_RUN_FAILED"


def _review_error(code: str, location: str, message: str, *, exit_code: int) -> dict[str, Any]:
    return {"ok": False, "error_count": 1,
            "errors": [{"code": code, "location": location, "message": message}], "exit_code": exit_code}


def _snapshot_bounds(args: argparse.Namespace) -> SnapshotBounds:
    return SnapshotBounds(
        max_files=int(getattr(args, "max_files", 200) or 200),
        max_diff_bytes=int(getattr(args, "max_diff_bytes", 1_000_000) or 1_000_000),
        max_blob_bytes=int(getattr(args, "max_blob_bytes", 200_000) or 200_000),
        max_file_bytes=int(getattr(args, "max_file_bytes", 100_000) or 100_000),
    )


def _apply_scope_options(args: argparse.Namespace, policy_override: dict) -> dict:
    if bool(getattr(args, "code_only", False)):
        policy_override = {
            **policy_override,
            "input_scope": {"mode": "code_only"},
        }
    if bool(getattr(args, "all_files", False)):
        policy_override = {
            **policy_override,
            "input_scope": {"mode": "all_files"},
        }
    return policy_override


def _run_snapshot_review(args, service, review_command, bounds, policy_override, policy_path):
    if review_command == "pr":
        return service.run_pr(
            remote=str(args.remote),
            repo=str(args.repo),
            pr=int(args.pr),
            repo_root=Path(str(args.repo_root)).resolve(),
            bounds=bounds,
            cli_policy_overrides=policy_override,
            policy_path=policy_path,
            fail_on_blocked=bool(args.fail_on_blocked),
            token=str(args.token or ""),
        )
    if review_command == "diff":
        return service.run_diff(
            repo_root=Path(str(args.repo_root)).resolve(),
            base_ref=str(args.base),
            head_ref=str(args.head),
            bounds=bounds,
            cli_policy_overrides=policy_override,
            policy_path=policy_path,
            fail_on_blocked=bool(args.fail_on_blocked),
        )
    return service.run_files(
        repo_root=Path(str(args.repo_root)).resolve(),
        ref=str(args.ref),
        paths=[str(item) for item in list(args.paths or [])],
        bounds=bounds,
        cli_policy_overrides=policy_override,
        policy_path=policy_path,
        fail_on_blocked=bool(args.fail_on_blocked),
    )


def _run_review_replay(args: argparse.Namespace, service: ReviewRunService):
    run_dir_raw = str(args.run_dir or "").strip()
    run_dir = Path(run_dir_raw).resolve() if run_dir_raw else None
    snapshot_path = Path(str(args.snapshot)).resolve() if str(args.snapshot).strip() else None
    policy_source_path = Path(str(args.policy)).resolve() if str(args.policy).strip() else None
    if run_dir is None and (snapshot_path is None or policy_source_path is None):
        return None, _review_error(ERROR_REVIEW_ARGUMENTS, "review.replay",
            "Provide --run-dir or both --snapshot and --policy.", exit_code=2)
    replay_bundle = load_review_replay_artifacts(
        run_dir=run_dir,
        snapshot_path=snapshot_path,
        policy_path=policy_source_path,
    )
    snapshot_payload = dict(replay_bundle.get("snapshot") or {})
    policy_payload = dict(replay_bundle.get("policy_resolved") or {})
    snapshot = ReviewSnapshot.from_dict(snapshot_payload)
    policy_only = dict(policy_payload)
    policy_only.pop("policy_digest", None)
    run_result = service.replay(
        repo_root=Path(str(args.repo_root)).resolve(),
        snapshot=snapshot,
        resolved_policy_payload=policy_only,
        fail_on_blocked=bool(args.fail_on_blocked),
    )
    return run_result, None


def handle_review_command(args: argparse.Namespace) -> int:
    bounds = _snapshot_bounds(args)
    policy_override = {}
    if bool(getattr(args, "enable_model_assisted", False)):
        policy_override = {
            "model_assisted": {"enabled": True},
            "lanes": {"enabled": ["deterministic", "model_assisted"]},
        }
    if bool(getattr(args, "code_only", False)) and bool(getattr(args, "all_files", False)):
        result = _review_error(ERROR_REVIEW_ARGUMENTS, "review.scope",
                              "Use only one of --code-only or --all-files.", exit_code=2)
        return emit_result(result, emit_json=bool(getattr(args, "json", False)))
    policy_override = _apply_scope_options(args, policy_override)
    policy_path = Path(args.policy).resolve() if str(getattr(args, "policy", "")).strip() else None
    service = ReviewRunService(workspace=Path(str(args.workspace)).resolve())
    review_command = str(getattr(args, "review_command", "")).strip()
    try:
        if review_command in {"pr", "diff", "files"}:
            run_result = _run_snapshot_review(args, service, review_command, bounds, policy_override, policy_path)
        elif review_command == "replay":
            run_result, error = _run_review_replay(args, service)
            if error is not None:
                return emit_result(error, emit_json=bool(getattr(args, "json", False)))
        else:
            result = _review_error(ERROR_REVIEW_ARGUMENTS, "review", "Unsupported review command.", exit_code=2)
            return emit_result(result, emit_json=bool(getattr(args, "json", False)))
        result = run_result.to_dict()
        result["verbose"] = bool(getattr(args, "verbose", False))
    except ReviewBundleError as exc:
        result = _review_error(str(exc.error_code or ERROR_REVIEW_RUN_FAILED),
                              str(exc.field or f"review.{review_command or 'unknown'}"), str(exc), exit_code=1)
        return emit_result(result, emit_json=bool(getattr(args, "json", False)))
    except (RuntimeError, ValueError, TypeError, OSError, json.JSONDecodeError, httpx.HTTPError) as exc:
        result = _review_error(ERROR_REVIEW_RUN_FAILED, f"review.{review_command or 'unknown'}", str(exc), exit_code=1)
        return emit_result(result, emit_json=bool(getattr(args, "json", False)))
    return emit_result(result, emit_json=bool(getattr(args, "json", False)))
