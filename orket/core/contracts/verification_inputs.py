"""Pure fixture-value admission and explicit verification-time normalization."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import AwareDatetime, TypeAdapter, ValidationError

from orket.core.contracts.value_capture import capture_builtin_values
from orket.schema import IssueVerification, VerificationScenario

FIXTURE_INPUT_ERROR = "E_FIXTURE_VERIFICATION_INPUT_UNSUPPORTED"
_VERIFICATION_TIME = TypeAdapter(AwareDatetime)


def verification_timestamp(observed_at: datetime) -> str:
    try:
        return _VERIFICATION_TIME.validate_python(observed_at, strict=True).astimezone(UTC).isoformat()
    except ValidationError as exc:
        raise ValueError("E_VERIFICATION_TIME_REQUIRES_AWARE_DATETIME") from exc


def capture_fixture_verification(verification: IssueVerification) -> IssueVerification:
    """Detach consumed values; the original model remains the publication target."""
    if type(verification) is not IssueVerification or type(verification.scenarios) is not list:
        raise TypeError(FIXTURE_INPUT_ERROR)
    scenarios = []
    for scenario in verification.scenarios:
        if type(scenario) is not VerificationScenario:
            raise TypeError(FIXTURE_INPUT_ERROR)
        scenarios.append({"id": scenario.id, "description": scenario.description,
                          "input_data": scenario.input_data, "expected_output": scenario.expected_output,
                          "actual_output": scenario.actual_output, "status": scenario.status})
    captured = capture_builtin_values({"fixture_path": verification.fixture_path, "scenarios": scenarios},
                                      error_code=FIXTURE_INPUT_ERROR)
    try:
        return IssueVerification.model_validate(captured)
    except ValidationError as exc:
        raise TypeError(FIXTURE_INPUT_ERROR) from exc
