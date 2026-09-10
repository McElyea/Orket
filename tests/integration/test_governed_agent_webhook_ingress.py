# Layer: integration

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.adapters.storage.async_governed_agent_webhook_repository import (
    AsyncGovernedAgentWebhookRepository,
)
from orket.application.services.governed_agent_webhook_ingress_service import (
    GovernedAgentWebhookIngressService,
    governed_agent_webhook_signature,
)
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.integration

_ISSUER = "integration:fixture"
_KEY_ID = "key:test-1"
_SECRET = "test-only-webhook-secret"
_NOW = "2026-09-07T18:00:00.000000Z"


def _body(*, workload_id: str = "governed-agent-loop") -> bytes:
    payload = {
        "target_kind": "new_run",
        "workload_id": workload_id,
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1",
            "request": agent_request(),
            "creation_timestamp_utc": "2026-09-07T18:00:00Z",
            "decision_timestamps_utc": [
                "2026-09-07T18:00:01Z",
                "2026-09-07T18:00:02Z",
            ],
            "next_lease_expiries_utc": ["2026-09-07T18:05:00Z"],
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _service(db_path: Path) -> GovernedAgentWebhookIngressService:
    return GovernedAgentWebhookIngressService(
        repository=AsyncGovernedAgentWebhookRepository(db_path),
        now_utc=lambda: _NOW,
        issuer_ref=_ISSUER,
        key_id=_KEY_ID,
        secret=_SECRET,
        replay_window_seconds=300,
    )


def _signature(body: bytes, *, delivery_id: str = "delivery-1", timestamp: str = _NOW) -> str:
    return governed_agent_webhook_signature(
        secret=_SECRET,
        issuer_ref=_ISSUER,
        delivery_id=delivery_id,
        delivered_at_utc=timestamp,
        body=body,
    )


async def _deliver(
    service: GovernedAgentWebhookIngressService,
    body: bytes,
    *,
    delivery_id: str = "delivery-1",
    timestamp: str = _NOW,
):
    return await service.deliver(
        issuer_ref=_ISSUER,
        delivery_id=delivery_id,
        delivered_at_utc=timestamp,
        key_id=_KEY_ID,
        signature=_signature(body, delivery_id=delivery_id, timestamp=timestamp),
        body=body,
    )


@pytest.mark.asyncio
async def test_webhook_delivery_is_durable_idempotent_and_conflict_detecting(tmp_path: Path) -> None:
    """Layer: integration. Authenticated delivery and selected wake survive restart atomically."""
    db_path = tmp_path / "agent.sqlite3"
    body = _body()
    service = _service(db_path)

    admitted = await _deliver(service, body)
    replayed = await _deliver(service, body)
    contradicted = await _deliver(service, _body(workload_id="other-workload"))

    assert admitted.status == "enqueued" and admitted.wake is not None
    assert replayed.status == "idempotent" and replayed.wake == admitted.wake
    assert contradicted.status == "conflict" and contradicted.delivery == admitted.delivery
    assert admitted.wake.source == "webhook"
    trigger = admitted.wake.payload["trigger"]
    assert trigger["schema_version"] == "governed_agent_webhook_trigger.v1"
    assert trigger["delivery_id"] == "delivery-1"
    assert trigger["content_digest"] == admitted.delivery.content_digest
    assert "signature" not in admitted.delivery.request

    restarted = _service(db_path)
    assert await restarted.list_deliveries(issuer_ref=_ISSUER) == (admitted.delivery,)
    assert await AsyncGovernedAgentWakeRepository(db_path).list_wakes() == (admitted.wake,)


@pytest.mark.asyncio
async def test_webhook_authentication_and_replay_window_fail_closed(tmp_path: Path) -> None:
    """Layer: integration. Identity, HMAC, canonical time, and body validation fail closed."""
    service = _service(tmp_path / "agent.sqlite3")
    body = _body()
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_SIGNATURE_INVALID"):
        await service.deliver(
            issuer_ref=_ISSUER,
            delivery_id="delivery-1",
            delivered_at_utc=_NOW,
            key_id=_KEY_ID,
            signature="sha256=" + "0" * 64,
            body=b"not-json",
        )
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_TIMESTAMP_EXPIRED"):
        await _deliver(service, body, timestamp="2026-09-07T17:54:59.000000Z")
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_TIMESTAMP_FUTURE"):
        await _deliver(service, body, timestamp="2026-09-07T18:05:01.000000Z")
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_TIMESTAMP_NONCANONICAL"):
        await service.deliver(
            issuer_ref=_ISSUER,
            delivery_id="delivery-1",
            delivered_at_utc="2026-09-07T18:00:00Z",
            key_id=_KEY_ID,
            signature=_signature(body),
            body=body,
        )
    invalid_json = b"not-json"
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_BODY_INVALID"):
        await service.deliver(
            issuer_ref=_ISSUER,
            delivery_id="delivery-2",
            delivered_at_utc=_NOW,
            key_id=_KEY_ID,
            signature=_signature(invalid_json, delivery_id="delivery-2"),
            body=invalid_json,
        )
    oversized = b"x" * 1_048_577
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_BODY_TOO_LARGE"):
        await service.deliver(
            issuer_ref=_ISSUER,
            delivery_id="delivery-3",
            delivered_at_utc=_NOW,
            key_id=_KEY_ID,
            signature=_signature(oversized, delivery_id="delivery-3"),
            body=oversized,
        )


@pytest.mark.asyncio
async def test_webhook_receipt_failure_rolls_back_selected_wake(tmp_path: Path) -> None:
    """Layer: integration. Receipt failure cannot leave an authority-free webhook wake."""
    db_path = tmp_path / "agent.sqlite3"
    service = _service(db_path)
    await service.list_deliveries(issuer_ref=_ISSUER)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TRIGGER reject_webhook_delivery
            BEFORE INSERT ON governed_agent_webhook_deliveries
            BEGIN SELECT RAISE(ABORT, 'forced webhook receipt failure'); END
            """
        )
        await conn.commit()

    with pytest.raises(aiosqlite.IntegrityError, match="forced webhook receipt failure"):
        await _deliver(service, _body(), delivery_id="delivery-rollback")

    assert await AsyncGovernedAgentWakeRepository(db_path).list_wakes() == ()


@pytest.mark.asyncio
async def test_webhook_configuration_must_be_complete() -> None:
    """Layer: contract. Disabled webhook ingress fails closed without inspecting the body."""
    service = GovernedAgentWebhookIngressService(
        repository=AsyncGovernedAgentWebhookRepository(":memory:"),
        now_utc=lambda: _NOW,
        issuer_ref=None,
        key_id=None,
        secret=None,
        replay_window_seconds=300,
    )
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_NOT_CONFIGURED"):
        await service.deliver(
            issuer_ref=_ISSUER,
            delivery_id="delivery-1",
            delivered_at_utc=_NOW,
            key_id=_KEY_ID,
            signature=None,
            body=b"",
        )
