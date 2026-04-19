from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from orket.application.terraform_review.models import TerraformPlanReviewRequest
from orket.application.terraform_review.service import TerraformPlanReviewService


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class LiveTerraformReviewConfig:
    plan_s3_uri: str = ""
    model_id: str = ""
    region: str = ""
    table_name: str = "TerraformReviews"
    created_at: str = ""
    execution_trace_ref: str = "terraform-plan-review-live-smoke"
    policy_bundle_id: str = "terraform_plan_reviewer_v1"
    forbidden_operations: list[str] = field(default_factory=lambda: ["destroy", "replace"])


def live_config_from_env() -> LiveTerraformReviewConfig:
    return LiveTerraformReviewConfig(
        plan_s3_uri=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", ""),
        model_id=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", ""),
        region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "",
        table_name=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE", "TerraformReviews"),
        created_at=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT", now_utc_iso()),
        execution_trace_ref=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF", "terraform-plan-review-live-smoke"),
        policy_bundle_id=os.getenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID", "terraform_plan_reviewer_v1"),
    )


def missing_required_env(config: LiveTerraformReviewConfig) -> list[str]:
    missing: list[str] = []
    if not str(config.plan_s3_uri).strip():
        missing.append("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI")
    if not str(config.model_id).strip():
        missing.append("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID")
    if not str(config.region).strip():
        missing.append("AWS_REGION")
    return missing


def is_environment_blocker(exc: Exception) -> bool:
    name = exc.__class__.__name__
    text = str(exc)
    return name in {"NoCredentialsError", "NoRegionError", "EndpointConnectionError"} or any(
        token in text for token in ("UnrecognizedClientException", "AccessDenied", "expired token")
    )


def parse_s3_bucket_key(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"invalid_s3_uri:{uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _s3_bucket_key(uri: str) -> tuple[str, str]:
    return parse_s3_bucket_key(uri)


class LiveS3Reader:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def read_object(self, uri: str) -> bytes:
        bucket, key = _s3_bucket_key(uri)

        def _read() -> bytes:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(_read)


class LiveBedrockSummarizer:
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
        text_parts = [
            str(item.get("text") or "").strip()
            for item in list(payload.get("content") or [])
            if isinstance(item, dict) and str(item.get("type") or "") == "text"
        ]
        summary = " ".join(part for part in text_parts if part).strip()
        return {
            "summary": summary,
            "review_focus_areas": ["Validate live smoke adapter path."],
            "raw_completion_ref": str(payload.get("id") or "bedrock.invoke_model"),
        }


class RecordingDynamoPublisher:
    def __init__(self, table: Any) -> None:
        self.table = table
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        self.calls.append((table_name, dict(item)))
        await asyncio.to_thread(self.table.put_item, Item=item)


async def run_live_review(
    *,
    workspace: Path,
    config: LiveTerraformReviewConfig,
) -> tuple[Any, RecordingDynamoPublisher]:
    import boto3  # type: ignore[import-not-found]

    s3_client = boto3.client("s3", region_name=str(config.region))
    bedrock_client = boto3.client("bedrock-runtime", region_name=str(config.region))
    dynamo_table = boto3.resource("dynamodb", region_name=str(config.region)).Table(str(config.table_name))
    publisher = RecordingDynamoPublisher(dynamo_table)
    service = TerraformPlanReviewService(
        workspace=workspace,
        s3_reader=LiveS3Reader(s3_client),
        model_summarizer=LiveBedrockSummarizer(bedrock_client, str(config.model_id)),
        audit_publisher=publisher,
        audit_table_name=str(config.table_name),
    )
    result = await service.run(
        TerraformPlanReviewRequest(
            plan_s3_uri=str(config.plan_s3_uri),
            forbidden_operations=list(config.forbidden_operations),
            request_metadata={"mode": "live_smoke"},
            policy_bundle_id=str(config.policy_bundle_id),
            execution_trace_ref=str(config.execution_trace_ref),
            created_at=str(config.created_at),
            model_id=str(config.model_id),
        )
    )
    return result, publisher
