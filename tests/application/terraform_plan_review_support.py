from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.proof.terraform_plan_review_fixture_support import (
    FakeAuditPublisher,
    FakeModelSummarizer,
    FakeS3Reader,
    FixtureCase,
    load_fixture_case,
    load_fixture_manifest,
    run_fixture_case as _run_fixture_case,
)


async def run_fixture_case(
    *,
    tmp_path: Path,
    case_name: str,
    model_payload: dict[str, Any] | None = None,
    model_error: Exception | None = None,
    model_factory: Any = None,
    prohibited_capability_attempt: str = "",
    s3_error: Exception | None = None,
    audit_error: Exception | None = None,
) -> tuple[Any, FixtureCase, FakeS3Reader, FakeModelSummarizer, FakeAuditPublisher]:
    return await _run_fixture_case(
        workspace=tmp_path / "workspace",
        case_name=case_name,
        model_payload=model_payload,
        model_error=model_error,
        model_factory=model_factory,
        prohibited_capability_attempt=prohibited_capability_attempt,
        s3_error=s3_error,
        audit_error=audit_error,
    )
