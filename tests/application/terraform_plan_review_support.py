from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.terraform_review.models import TerraformPlanReviewRequest
from orket.application.terraform_review.service import TerraformPlanReviewService

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "terraform_plan_reviewer_v1"


@dataclass(slots=True)
class FixtureCase:
    name: str
    plan_s3_uri: str
    plan_bytes: bytes
    forbidden_operations: list[str]
    expected_verdict: str
    expected_publish_decision: str
    expected_summary_status: str
    expected_final_verdict_source: str
    expected_deterministic_analysis_complete: bool
    expected_action_counts: dict[str, int]


def load_fixture_manifest() -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / "fixture_manifest.json").read_text(encoding="utf-8"))


def load_fixture_case(name: str) -> FixtureCase:
    manifest = load_fixture_manifest()
    payload = dict(manifest[name])
    plan_path = FIXTURE_ROOT / str(payload["plan_path"])
    return FixtureCase(
        name=name,
        plan_s3_uri=f"s3://terraform-review-fixtures/{plan_path.name}",
        plan_bytes=plan_path.read_bytes(),
        forbidden_operations=list(payload["forbidden_operations"]),
        expected_verdict=str(payload["expected_verdict"]),
        expected_publish_decision=str(payload["expected_publish_decision"]),
        expected_summary_status=str(payload["expected_summary_status"]),
        expected_final_verdict_source=str(payload["expected_final_verdict_source"]),
        expected_deterministic_analysis_complete=bool(payload["expected_deterministic_analysis_complete"]),
        expected_action_counts=dict(payload["expected_action_counts"]),
    )


class FakeS3Reader:
    def __init__(self, objects: dict[str, bytes], *, errors: dict[str, Exception] | None = None) -> None:
        self.objects = dict(objects)
        self.errors = dict(errors or {})
        self.calls: list[str] = []

    async def read_object(self, uri: str) -> bytes:
        self.calls.append(uri)
        if uri in self.errors:
            raise self.errors[uri]
        if uri not in self.objects:
            raise FileNotFoundError(f"missing_fixture_object:{uri}")
        return self.objects[uri]


class FakeModelSummarizer:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        error: Exception | None = None,
        factory: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.payload = dict(payload or {})
        self.error = error
        self.factory = factory
        self.calls: list[dict[str, Any]] = []

    async def summarize(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(request))
        if self.error is not None:
            raise self.error
        if self.factory is not None:
            return dict(self.factory(dict(request)))
        if self.payload:
            return dict(self.payload)
        return {
            "summary": "Deterministic review completed.",
            "review_focus_areas": ["Validate policy-sensitive Terraform actions."],
            "raw_completion_ref": "fake:model:001",
        }


class FakeAuditPublisher:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        self.calls.append((table_name, dict(item)))
        if self.error is not None:
            raise self.error


async def run_fixture_case(
    *,
    tmp_path: Path,
    case_name: str,
    model_payload: dict[str, Any] | None = None,
    model_error: Exception | None = None,
    model_factory: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    prohibited_capability_attempt: str = "",
    s3_error: Exception | None = None,
    audit_error: Exception | None = None,
) -> tuple[Any, FixtureCase, FakeS3Reader, FakeModelSummarizer, FakeAuditPublisher]:
    case = load_fixture_case(case_name)
    s3_reader = FakeS3Reader(
        {case.plan_s3_uri: case.plan_bytes},
        errors={case.plan_s3_uri: s3_error} if s3_error is not None else None,
    )
    model = FakeModelSummarizer(payload=model_payload, error=model_error, factory=model_factory)
    publisher = FakeAuditPublisher(error=audit_error)
    service = TerraformPlanReviewService(
        workspace=tmp_path / "workspace",
        s3_reader=s3_reader,
        model_summarizer=model,
        audit_publisher=publisher,
    )
    result = await service.run(
        TerraformPlanReviewRequest(
            plan_s3_uri=case.plan_s3_uri,
            forbidden_operations=list(case.forbidden_operations),
            request_metadata={"fixture": case.name},
            policy_bundle_id="terraform_plan_reviewer_v1",
            execution_trace_ref=f"trace-{case.name}",
            created_at="2026-03-22T00:00:00Z",
            model_id="bedrock.fake",
            prohibited_capability_attempt=prohibited_capability_attempt,
        )
    )
    return result, case, s3_reader, model, publisher
