"""Application capture of credential key, time and cryptographic identity sources."""

from __future__ import annotations

from collections.abc import Mapping

from orket.application.services.kernel_invocation_inputs import capture_kernel_environment
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.kernel_credentials import CredentialIssueInputs, CredentialObservation


def capture_credential_key(*, environment: Mapping[str, str] | None = None) -> bytes:
    observed = capture_kernel_environment(environment).values
    configured = str(observed.get("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY") or "").strip()
    # Preserve the documented development behavior; this is not production key provisioning.
    return configured.encode("utf-8") if configured else b"orket-nervous-system-dev-hmac-key"


def capture_credential_observation(
    *,
    environment: Mapping[str, str] | None = None,
    runtime_inputs: RuntimeInputService | None = None,
) -> CredentialObservation:
    key = capture_credential_key(environment=environment)
    runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
    return CredentialObservation(observed_at=runtime_inputs.utc_now(), hmac_key=key)


def capture_credential_issue_inputs(
    *,
    environment: Mapping[str, str] | None = None,
    runtime_inputs: RuntimeInputService | None = None,
) -> CredentialIssueInputs:
    runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
    observed = capture_credential_observation(environment=environment, runtime_inputs=runtime_inputs)
    return CredentialIssueInputs(
        observed_at=observed.observed_at,
        hmac_key=observed.hmac_key,
        raw_token=runtime_inputs.create_secret_token(),
        token_id=runtime_inputs.create_credential_token_id(),
    )
