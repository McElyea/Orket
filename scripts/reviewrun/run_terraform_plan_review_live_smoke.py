from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

from scripts.proof.terraform_plan_review_live_support import (
    LiveTerraformReviewConfig,
    is_environment_blocker,
    live_config_from_env,
    missing_required_env,
    now_utc_iso,
    run_live_review,
)


DEFAULT_OUTPUT = Path(".orket/durable/observability/terraform_plan_review_live_smoke.json")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = live_config_from_env()
    parser = argparse.ArgumentParser(description="Run the Terraform plan reviewer thin live AWS smoke path.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--plan-s3-uri", default=env.plan_s3_uri)
    parser.add_argument("--model-id", default=env.model_id)
    parser.add_argument("--region", default=env.region)
    parser.add_argument("--table-name", default=env.table_name)
    parser.add_argument("--created-at", default=env.created_at or now_utc_iso())
    parser.add_argument(
        "--execution-trace-ref",
        default=env.execution_trace_ref,
    )
    parser.add_argument(
        "--policy-bundle-id",
        default=env.policy_bundle_id,
    )
    return parser.parse_args(argv)


def _environment_blocker(*, args: argparse.Namespace, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "path": "blocked",
        "result": "environment blocker",
        "reason": reason,
        "publish_decision": "no_publish",
        "execution_status": "environment_blocker",
        "policy_bundle_id": str(args.policy_bundle_id),
        "execution_trace_ref": str(args.execution_trace_ref),
        "created_at": str(args.created_at),
    }


def _runtime_failure(*, args: argparse.Namespace, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "failure",
        "path": "blocked",
        "result": "failure",
        "reason": reason,
        "publish_decision": "no_publish",
        "execution_status": "failure",
        "policy_bundle_id": str(args.policy_bundle_id),
        "execution_trace_ref": str(args.execution_trace_ref),
        "created_at": str(args.created_at),
    }


async def _run_live_smoke(args: argparse.Namespace) -> dict[str, Any]:
    config = LiveTerraformReviewConfig(
        plan_s3_uri=str(args.plan_s3_uri),
        model_id=str(args.model_id),
        region=str(args.region),
        table_name=str(args.table_name),
        created_at=str(args.created_at),
        execution_trace_ref=str(args.execution_trace_ref),
        policy_bundle_id=str(args.policy_bundle_id),
    )
    missing = missing_required_env(config)
    if missing:
        return _environment_blocker(args=args, reason=f"missing_required_env:{','.join(missing)}")

    try:
        result, _publisher = await run_live_review(workspace=Path.cwd(), config=config)
    except ModuleNotFoundError:
        return _environment_blocker(args=args, reason="missing_dependency:boto3")
    except Exception as exc:  # noqa: BLE001 - top-level smoke boundary
        if is_environment_blocker(exc):
            return _environment_blocker(args=args, reason=str(exc))
        return _runtime_failure(args=args, reason=str(exc))

    return {
        "ok": bool(result.ok),
        "status": result.governance_artifact.execution_status,
        "path": result.governance_artifact.observed_path_classification,
        "result": result.governance_artifact.observed_result_classification,
        "publish_decision": result.governance_artifact.publish_decision,
        "summary_status": result.governance_artifact.summary_status,
        "final_verdict_source": result.governance_artifact.final_verdict_source,
        "artifact_dir": result.artifact_bundle.artifact_dir,
        "policy_bundle_id": result.governance_artifact.policy_bundle_id,
        "execution_trace_ref": result.governance_artifact.execution_trace_ref,
        "created_at": str(args.created_at),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = asyncio.run(_run_live_smoke(args))
    out_path = Path(str(args.out))
    write_payload_with_diff_ledger(out_path, payload)
    print(json.dumps({"ok": bool(payload.get("ok")), "out": str(out_path), "status": str(payload.get("status"))}))
    return 0 if str(payload.get("result")) == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
