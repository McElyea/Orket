from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from orket.application.services.governed_agent_wake_ingress_service import (
    GovernedAgentWakeSubmission,
)
from orket.application.services.governed_agent_webhook_records import (
    GovernedAgentWebhookDeliveryRecord,
    GovernedAgentWebhookDeliveryRequest,
    GovernedAgentWebhookDeliveryResult,
    GovernedAgentWebhookRepository,
)
from orket_extension_sdk import canonical_digest_sha256

_SIGNATURE_PATTERN = re.compile(r"sha256=([0-9a-f]{64})")
_SIGNATURE_DOMAIN = "orket-governed-agent-webhook.v1"
GOVERNED_AGENT_WEBHOOK_MAX_BODY_BYTES = 1_048_576


class GovernedAgentWebhookIngressService:
    """Authenticate and retain external wake deliveries before dispatch."""

    def __init__(
        self,
        *,
        repository: GovernedAgentWebhookRepository,
        now_utc: Callable[[], str],
        issuer_ref: str | None,
        key_id: str | None,
        secret: str | None,
        replay_window_seconds: int,
        notify_ready: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._now_utc = now_utc
        self._issuer_ref = _optional_identity(issuer_ref)
        self._key_id = _optional_identity(key_id)
        self._secret = None if secret is None else secret.encode("utf-8")
        self._replay_window_seconds = replay_window_seconds
        self._notify_ready = notify_ready

    async def deliver(
        self,
        *,
        issuer_ref: str,
        delivery_id: str,
        delivered_at_utc: str | None,
        key_id: str | None,
        signature: str | None,
        body: bytes,
    ) -> GovernedAgentWebhookDeliveryResult:
        configured_issuer, configured_key, secret = self._configuration()
        issuer = _identity(issuer_ref, "E_AGENT_WEBHOOK_ISSUER_REQUIRED")
        delivery = _identity(delivery_id, "E_AGENT_WEBHOOK_DELIVERY_ID_REQUIRED")
        supplied_key = _identity(key_id, "E_AGENT_WEBHOOK_KEY_ID_REQUIRED")
        timestamp = _canonical_utc(delivered_at_utc, "E_AGENT_WEBHOOK_TIMESTAMP")
        received_at = _normalized_utc(self._now_utc(), "E_AGENT_WEBHOOK_CLOCK")
        if not hmac.compare_digest(issuer, configured_issuer):
            raise ValueError("E_AGENT_WEBHOOK_ISSUER_INVALID")
        if not hmac.compare_digest(supplied_key, configured_key):
            raise ValueError("E_AGENT_WEBHOOK_KEY_ID_INVALID")
        _verify_freshness(timestamp, received_at, self._replay_window_seconds)
        _verify_signature(
            secret=secret,
            issuer_ref=issuer,
            delivery_id=delivery,
            delivered_at_utc=timestamp,
            body=body,
            signature=signature,
        )
        parsed_body = _body_mapping(body)
        delivery_ref = _delivery_ref(issuer, delivery)
        submission = _submission(parsed_body, occurrence_id=delivery_ref)
        content_digest = _content_digest(body)
        request_payload = {
            "schema_version": "governed_agent_webhook_delivery.v1",
            "delivery_ref": delivery_ref,
            "issuer_ref": issuer,
            "delivery_id": delivery,
            "key_id": supplied_key,
            "delivered_at_utc": timestamp,
            "content_digest": content_digest,
            "body": dict(parsed_body),
        }
        wake = submission.to_request(
            source="webhook",
            created_at_utc=received_at,
            trigger=_trigger_payload(request_payload, received_at),
        )
        result = await self._repository.apply_delivery(
            GovernedAgentWebhookDeliveryRequest(
                delivery_ref=delivery_ref,
                issuer_ref=issuer,
                delivery_id=delivery,
                key_id=supplied_key,
                delivered_at_utc=timestamp,
                received_at_utc=received_at,
                request=request_payload,
                selected_wake=wake,
            )
        )
        if (
            result.status in {"enqueued", "idempotent"}
            and result.wake is not None
            and result.wake.state == "queued"
            and self._notify_ready is not None
        ):
            self._notify_ready()
        return result

    async def list_deliveries(
        self,
        *,
        issuer_ref: str,
    ) -> tuple[GovernedAgentWebhookDeliveryRecord, ...]:
        issuer = _identity(issuer_ref, "E_AGENT_WEBHOOK_ISSUER_REQUIRED")
        return await self._repository.list_deliveries(issuer_ref=issuer)

    def configured(self) -> bool:
        return bool(self._issuer_ref and self._key_id and self._secret)

    def _configuration(self) -> tuple[str, str, bytes]:
        if not self.configured() or self._secret is None:
            raise ValueError("E_AGENT_WEBHOOK_NOT_CONFIGURED")
        return str(self._issuer_ref), str(self._key_id), self._secret


def governed_agent_webhook_delivery_view(
    delivery: GovernedAgentWebhookDeliveryRecord,
) -> dict[str, Any]:
    return {
        "delivery_ref": delivery.delivery_ref,
        "issuer_ref": delivery.issuer_ref,
        "delivery_id": delivery.delivery_id,
        "key_id": delivery.key_id,
        "delivered_at_utc": delivery.delivered_at_utc,
        "received_at_utc": delivery.received_at_utc,
        "request": dict(delivery.request),
        "request_digest": delivery.request_digest,
        "content_digest": delivery.content_digest,
        "status": delivery.status,
        "resulting_wake_id": delivery.resulting_wake_id,
    }


def governed_agent_webhook_signature(
    *,
    secret: str,
    issuer_ref: str,
    delivery_id: str,
    delivered_at_utc: str,
    body: bytes,
) -> str:
    key = secret.encode("utf-8")
    if not key:
        raise ValueError("E_AGENT_WEBHOOK_SECRET_REQUIRED")
    message = _signature_message(
        issuer_ref=_identity(issuer_ref, "E_AGENT_WEBHOOK_ISSUER_REQUIRED"),
        delivery_id=_identity(delivery_id, "E_AGENT_WEBHOOK_DELIVERY_ID_REQUIRED"),
        delivered_at_utc=_canonical_utc(delivered_at_utc, "E_AGENT_WEBHOOK_TIMESTAMP"),
        body=body,
    )
    return "sha256=" + hmac.new(key, message, hashlib.sha256).hexdigest()


def _verify_signature(
    *,
    secret: bytes,
    issuer_ref: str,
    delivery_id: str,
    delivered_at_utc: str,
    body: bytes,
    signature: str | None,
) -> None:
    supplied = str(signature or "").strip()
    if _SIGNATURE_PATTERN.fullmatch(supplied) is None:
        raise ValueError("E_AGENT_WEBHOOK_SIGNATURE_INVALID")
    expected = "sha256=" + hmac.new(
        secret,
        _signature_message(
            issuer_ref=issuer_ref,
            delivery_id=delivery_id,
            delivered_at_utc=delivered_at_utc,
            body=body,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError("E_AGENT_WEBHOOK_SIGNATURE_INVALID")


def _signature_message(
    *,
    issuer_ref: str,
    delivery_id: str,
    delivered_at_utc: str,
    body: bytes,
) -> bytes:
    fields = (_SIGNATURE_DOMAIN, issuer_ref, delivery_id, delivered_at_utc, _content_digest(body))
    return "\n".join(fields).encode("utf-8")


def _submission(payload: Mapping[str, Any], *, occurrence_id: str) -> GovernedAgentWakeSubmission:
    allowed = {"target_kind", "target_run_id", "workload_id", "dispatch"}
    if set(payload) - allowed:
        raise ValueError("E_AGENT_WEBHOOK_FIELD_UNKNOWN")
    return GovernedAgentWakeSubmission.from_mapping({"occurrence_id": occurrence_id, **dict(payload)})


def _body_mapping(body: bytes) -> Mapping[str, Any]:
    if len(body) > GOVERNED_AGENT_WEBHOOK_MAX_BODY_BYTES:
        raise ValueError("E_AGENT_WEBHOOK_BODY_TOO_LARGE")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("E_AGENT_WEBHOOK_BODY_INVALID") from exc
    if not isinstance(value, Mapping):
        raise ValueError("E_AGENT_WEBHOOK_BODY_OBJECT_REQUIRED")
    return value


def _trigger_payload(request: Mapping[str, Any], received_at_utc: str) -> dict[str, Any]:
    return {
        "schema_version": "governed_agent_webhook_trigger.v1",
        "delivery_ref": request["delivery_ref"],
        "issuer_ref": request["issuer_ref"],
        "delivery_id": request["delivery_id"],
        "key_id": request["key_id"],
        "delivered_at_utc": request["delivered_at_utc"],
        "received_at_utc": received_at_utc,
        "content_digest": request["content_digest"],
    }


def _verify_freshness(delivered_at_utc: str, received_at_utc: str, window_seconds: int) -> None:
    delivered = _parse_utc(delivered_at_utc, "E_AGENT_WEBHOOK_TIMESTAMP")
    received = _parse_utc(received_at_utc, "E_AGENT_WEBHOOK_CLOCK")
    window = timedelta(seconds=window_seconds)
    if delivered < received - window:
        raise ValueError("E_AGENT_WEBHOOK_TIMESTAMP_EXPIRED")
    if delivered > received + window:
        raise ValueError("E_AGENT_WEBHOOK_TIMESTAMP_FUTURE")


def _delivery_ref(issuer_ref: str, delivery_id: str) -> str:
    digest = canonical_digest_sha256({"issuer_ref": issuer_ref, "delivery_id": delivery_id})
    return f"agent-webhook-delivery:{digest[:32]}"


def _content_digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _canonical_utc(value: object, code_prefix: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{code_prefix}_REQUIRED")
    parsed = _parse_utc(raw, code_prefix)
    canonical = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if raw != canonical:
        raise ValueError(f"{code_prefix}_NONCANONICAL")
    return canonical


def _normalized_utc(value: object, code_prefix: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{code_prefix}_REQUIRED")
    return _parse_utc(raw, code_prefix).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: str, code_prefix: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{code_prefix}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{code_prefix}_NOT_UTC")
    return parsed.astimezone(UTC)


def _identity(value: object, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(code)
    if len(normalized) > 200 or any(character in normalized for character in "\r\n"):
        raise ValueError(code.replace("_REQUIRED", "_INVALID"))
    return normalized


def _optional_identity(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
