"""Pure credential identities and decisions over explicit trusted observations."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialObservation:
    observed_at: datetime
    hmac_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.hmac_key) is not bytes or not self.hmac_key:
            raise ValueError("E_CREDENTIAL_KEY_REQUIRED")
        object.__setattr__(self, "observed_at", credential_observation_time(self.observed_at))


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialIssueInputs(CredentialObservation):
    raw_token: str = field(repr=False)
    token_id: str = field(repr=False)

    def __post_init__(self) -> None:
        CredentialObservation.__post_init__(self)
        if type(self.raw_token) is not str or not self.raw_token.strip():
            raise ValueError("E_CREDENTIAL_TOKEN_REQUIRED")
        if type(self.token_id) is not str or not self.token_id.strip():
            raise ValueError("E_CREDENTIAL_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class CredentialBinding:
    session_id: str
    proposal_digest: str
    tool_name: str
    scope_digest: str
    executor_instance_id: str
    expected_tool_profile_digest: str

    def __post_init__(self) -> None:
        _validate_plain_fields(self)


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    session_id: str
    proposal_digest: str
    tool_name: str
    scope_digest: str
    executor_instance_id: str
    tool_profile_digest: str
    expires_at: str
    used: bool
    invalidated: bool
    invalidation_reason: str

    def __post_init__(self) -> None:
        _validate_plain_fields(self, booleans=("used", "invalidated"))


def _validate_plain_fields(value: CredentialBinding | CredentialRecord, *, booleans: tuple[str, ...] = ()) -> None:
    if any(type(getattr(value, item.name)) is not (bool if item.name in booleans else str) for item in fields(value)):
        raise ValueError("E_CREDENTIAL_VALUE_INVALID")


def credential_hash(raw_token: str, inputs: CredentialObservation) -> str:
    return hmac.new(inputs.hmac_key, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def credential_id_hash(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def credential_observation_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("E_CREDENTIAL_OBSERVATION_REQUIRES_TIMEZONE")
    return value.astimezone(UTC)


def credential_refusal(record: CredentialRecord, binding: CredentialBinding, inputs: CredentialObservation) -> str:
    if (record.session_id, record.proposal_digest, record.tool_name, record.scope_digest) != (
        binding.session_id,
        binding.proposal_digest,
        binding.tool_name,
        binding.scope_digest,
    ):
        return "TOKEN_INVALID"
    if record.executor_instance_id and record.executor_instance_id != binding.executor_instance_id:
        return "TOKEN_INVALID"
    if binding.expected_tool_profile_digest and record.tool_profile_digest != binding.expected_tool_profile_digest:
        return "TOKEN_INVALID"
    if credential_is_expired(record.expires_at, inputs.observed_at):
        return "TOKEN_EXPIRED"
    if record.used:
        return "TOKEN_REPLAY"
    if record.invalidated:
        return {"expired": "TOKEN_EXPIRED", "used": "TOKEN_REPLAY"}.get(record.invalidation_reason, "TOKEN_INVALID")
    return ""


def credential_is_expired(expires_at: str, observed_at: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return observed_at >= parsed.astimezone(UTC)
