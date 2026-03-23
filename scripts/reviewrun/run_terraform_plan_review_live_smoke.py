from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

from orket.application.terraform_review.models import TerraformPlanReviewRequest
from orket.application.terraform_review.service import TerraformPlanReviewService


DEFAULT_OUTPUT = Path(".orket/durable/observability/terraform_plan_review_live_smoke.json")


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Terraform plan reviewer thin live AWS smoke path.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--plan-s3-uri", default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", ""))
    parser.add_argument("--model-id", default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", ""))
    parser.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "")
    parser.add_argument("--table-name", default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE", "TerraformReviews"))
    parser.add_argument("--created-at", default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT", _now_utc_iso()))
    parser.add_argument(
        "--execution-trace-ref",
        default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF", "terraform-plan-review-live-smoke"),
    )
    parser.add_argument(
        "--policy-bundle-id",
        default=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID", "terraform_plan_reviewer_v1"),
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


def _missing_required_env(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    if not str(args.plan_s3_uri).strip():
        missing.append("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI")
    if not str(args.model_id).strip():
        missing.append("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID")
    if not str(args.region).strip():
        missing.append("AWS_REGION")
    return missing


def _s3_bucket_key(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"invalid_s3_uri:{uri}")
    return parsed.netloc, parsed.path.lstrip("/")


class _LiveS3Reader:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def read_object(self, uri: str) -> bytes:
        bucket, key = _s3_bucket_key(uri)

        def _read() -> bytes:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(_read)


class _LiveBedrockSummarizer:
    def __init__(self, client: Any, model_id: str) -> None:
        self.client = client
        self.model_id = model_id

    async def summarize(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.model_id.startswith("anthropic."):
            raise RuntimeError(f"unsupported_bedrock_model_for_smoke:{self.model_id}")
        prompt = (
            "Explain this Terraform plan review result in 2 short sentences.\n"
            f"Risk verdict: {request.get('risk_verdict')}\n"
            f"Forbidden hits: {json.dumps(request.get('forbidden_operation_hits') or [])}\n"
            f"Action counts: {json.dumps(request.get('action_counts') or {})}\n"
        )
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 128,
                "temperature": 0,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            }
        )

        def _invoke() -> dict[str, Any]:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(response["body"].read())

        payload = await asyncio.to_thread(_invoke)
        content = list(payload.get("content") or [])
        text_parts = [
            str(item.get("text") or "").strip()
            for item in content
            if isinstance(item, dict) and str(item.get("type") or "") == "text"
        ]
        summary = " ".join(part for part in text_parts if part).strip()
        return {
            "summary": summary,
            "review_focus_areas": ["Validate live smoke adapter path."],
            "raw_completion_ref": str(payload.get("id") or "bedrock.invoke_model"),
        }


class _LiveDynamoPublisher:
    def __init__(self, table: Any) -> None:
        self.table = table

    async def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        del table_name
        await asyncio.to_thread(self.table.put_item, Item=item)


def _is_environment_blocker(exc: Exception) -> bool:
    name = exc.__class__.__name__
    text = str(exc)
    return name in {"NoCredentialsError", "NoRegionError", "EndpointConnectionError"} or any(
        token in text for token in ("UnrecognizedClientException", "AccessDenied", "expired token")
    )


async def _run_live_smoke(args: argparse.Namespace) -> dict[str, Any]:
    missing = _missing_required_env(args)
    if missing:
        return _environment_blocker(args=args, reason=f"missing_required_env:{','.join(missing)}")

    try:
        import boto3  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _environment_blocker(args=args, reason="missing_dependency:boto3")

    s3_client = boto3.client("s3", region_name=str(args.region))
    bedrock_client = boto3.client("bedrock-runtime", region_name=str(args.region))
    dynamo_table = boto3.resource("dynamodb", region_name=str(args.region)).Table(str(args.table_name))

    service = TerraformPlanReviewService(
        workspace=Path.cwd(),
        s3_reader=_LiveS3Reader(s3_client),
        model_summarizer=_LiveBedrockSummarizer(bedrock_client, str(args.model_id)),
        audit_publisher=_LiveDynamoPublisher(dynamo_table),
        audit_table_name=str(args.table_name),
    )
    try:
        result = await service.run(
            TerraformPlanReviewRequest(
                plan_s3_uri=str(args.plan_s3_uri),
                forbidden_operations=["destroy", "replace"],
                request_metadata={"mode": "live_smoke"},
                policy_bundle_id=str(args.policy_bundle_id),
                execution_trace_ref=str(args.execution_trace_ref),
                created_at=str(args.created_at),
                model_id=str(args.model_id),
            )
        )
    except Exception as exc:  # noqa: BLE001 - top-level smoke boundary
        if _is_environment_blocker(exc):
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
