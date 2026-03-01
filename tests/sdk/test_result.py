from __future__ import annotations

from pydantic import ValidationError

from orket_extension_sdk.result import Issue, WorkloadResult


def test_issue_severity_is_validated() -> None:
    try:
        Issue(code="X", message="bad", severity="fatal")
        raised = False
    except ValidationError:
        raised = True
    assert raised is True


def test_workload_result_defaults() -> None:
    result = WorkloadResult(ok=True)

    assert result.output == {}
    assert result.artifacts == []
    assert result.issues == []
    assert result.metrics == {}
