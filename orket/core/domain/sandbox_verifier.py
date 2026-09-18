"""Pure captured inputs and interpretation for sandbox HTTP observations."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from orket.core.contracts.protocol_hashing import canonical_json
from orket.schema import IssueVerification, VerificationResult, VerificationScenario
from orket_extension_sdk import FrozenJson


@dataclass(frozen=True)
class SandboxHttpRequest:
    scenario_id: str
    method: str
    url: str
    payload: FrozenJson


@dataclass(frozen=True)
class CapturedSandboxScenario:
    scenario_id: str
    definition: FrozenJson
    request: SandboxHttpRequest | None
    rejection: str | None = None


@dataclass(frozen=True)
class SandboxVerificationInput:
    sandbox_id: str
    timestamp: str
    base_url: str
    scenarios: tuple[CapturedSandboxScenario, ...]


@dataclass(frozen=True)
class SandboxHttpObservation:
    scenario_id: str
    status_code: int | None = None
    body: FrozenJson | None = None
    error: str | None = None


def capture_sandbox_verification(
    *, sandbox_id: str, base_url: str, timestamp: str, verification: IssueVerification,
) -> SandboxVerificationInput:
    if not isinstance(base_url, str) or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in base_url):
        raise ValueError("E_SANDBOX_HTTP_BASE_URL_INVALID")
    try:
        target = urlsplit(base_url)
        valid = (target.scheme in {"http", "https"} and target.hostname and target.port != 0
                 and target.username is None and target.password is None and not target.query and not target.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("E_SANDBOX_HTTP_BASE_URL_INVALID")
    # Model serialization would coerce unsupported dataclasses/models into JSON.
    definitions = tuple(FrozenJson(canonical_json(dict(s))) for s in verification.scenarios)
    identities = [definition.thaw()["id"] for definition in definitions]
    if len(set(identities)) != len(identities):
        raise ValueError("E_SANDBOX_SCENARIO_ID_DUPLICATE")
    captured = []
    for identity, definition in zip(identities, definitions, strict=True):
        inputs = VerificationScenario.model_validate(definition.thaw()).input_data
        endpoint, method = inputs.get("endpoint"), inputs.get("method", "GET")
        rejection = None
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            rejection = "E_SANDBOX_ENDPOINT_REQUIRED"
        elif not isinstance(method, str) or not method.isascii() or not method.isalpha():
            rejection = "E_SANDBOX_HTTP_METHOD_INVALID"
        request = None if rejection else SandboxHttpRequest(
            identity, method.upper(), base_url.rstrip("/") + endpoint, FrozenJson(canonical_json(inputs.get("payload"))),
        )
        captured.append(CapturedSandboxScenario(identity, definition, request, rejection))
    return SandboxVerificationInput(str(sandbox_id), timestamp, base_url, tuple(captured))


def interpret_sandbox_observations(
    captured: SandboxVerificationInput, observations: tuple[SandboxHttpObservation, ...],
) -> tuple[VerificationResult, tuple[VerificationScenario, ...]]:
    if tuple(item.scenario_id for item in captured.scenarios) != tuple(item.scenario_id for item in observations):
        raise ValueError("E_SANDBOX_OBSERVATION_IDENTITY_MISMATCH")
    logs = [f"--- Sandbox Verification Started for {captured.sandbox_id} at {captured.timestamp} ---"]
    logs.append(f"Target URL: {captured.base_url}")
    scenarios, passed = [], 0
    for item, observation in zip(captured.scenarios, observations, strict=True):
        scenario = VerificationScenario.model_validate(item.definition.thaw())
        scenario.actual_output = observation.body.thaw() if observation.body is not None else None
        error = item.rejection or observation.error
        status_matches = observation.status_code == scenario.input_data.get("expected_status", 200)
        body_matches = observation.body is not None and canonical_json(scenario.actual_output) == canonical_json(
            scenario.expected_output,
        )
        matched = not error and status_matches and body_matches
        scenario.status = "pass" if matched else "fail"
        passed += int(matched)
        reason = error or ("observed match" if matched else "status/body mismatch")
        logs.append(f"  [{scenario.status.upper()}] {scenario.id}: {reason}")
        scenarios.append(scenario)
    total = len(scenarios)
    if not total:
        logs.append("No HTTP scenarios configured; no empirical proof.")
    logs.append(f"--- Sandbox Verification Complete: {passed} Passed, {total - passed} Failed ---")
    result = VerificationResult(timestamp=captured.timestamp, total_scenarios=total,
                                passed=passed, failed=total - passed, logs=logs)
    return result, tuple(scenarios)
