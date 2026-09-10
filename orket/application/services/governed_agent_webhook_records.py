from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeRecord,
    GovernedAgentWakeRequest,
)

WebhookDeliveryStatus = Literal["enqueued", "idempotent", "conflict"]


@dataclass(frozen=True, slots=True)
class GovernedAgentWebhookDeliveryRequest:
    delivery_ref: str
    issuer_ref: str
    delivery_id: str
    key_id: str
    delivered_at_utc: str
    received_at_utc: str
    request: Mapping[str, Any]
    selected_wake: GovernedAgentWakeRequest


@dataclass(frozen=True, slots=True)
class GovernedAgentWebhookDeliveryRecord:
    delivery_ref: str
    issuer_ref: str
    delivery_id: str
    key_id: str
    delivered_at_utc: str
    received_at_utc: str
    request: Mapping[str, Any]
    request_digest: str
    content_digest: str
    status: WebhookDeliveryStatus
    resulting_wake_id: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWebhookDeliveryResult:
    status: WebhookDeliveryStatus
    delivery: GovernedAgentWebhookDeliveryRecord
    wake: GovernedAgentWakeRecord | None


class GovernedAgentWebhookRepository(Protocol):
    async def apply_delivery(
        self,
        request: GovernedAgentWebhookDeliveryRequest,
    ) -> GovernedAgentWebhookDeliveryResult: ...

    async def list_deliveries(
        self,
        *,
        issuer_ref: str,
    ) -> tuple[GovernedAgentWebhookDeliveryRecord, ...]: ...

    async def get_delivery(
        self,
        *,
        delivery_ref: str,
    ) -> GovernedAgentWebhookDeliveryRecord | None: ...
