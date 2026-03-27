# Layer: integration

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.coordinator_api as coordinator_api_module
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_lease_service import CoordinatorControlPlaneLeaseService
from orket.application.services.coordinator_control_plane_reservation_service import (
    CoordinatorControlPlaneReservationService,
)
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus
from orket.core.domain.coordinator_card import Card
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.integration


def _client(*, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        coordinator_api_module.app,
        raise_server_exceptions=raise_server_exceptions,
    )


def _card(*, state: str, claimed_by: str | None = None, lease_expires_at: float | None = None) -> Card:
    return Card(
        id="card-1",
        payload={"task": "demo"},
        state=state,
        claimed_by=claimed_by,
        lease_expires_at=lease_expires_at,
        result=None,
        attempts=0,
        hedged_execution=False,
    )


def _install_in_memory_control_plane(monkeypatch: pytest.MonkeyPatch) -> InMemoryControlPlaneRecordRepository:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    monkeypatch.setattr(coordinator_api_module, "control_plane_repository", repository)
    monkeypatch.setattr(coordinator_api_module, "control_plane_publication", publication)
    monkeypatch.setattr(
        coordinator_api_module,
        "control_plane_lease_service",
        CoordinatorControlPlaneLeaseService(publication=publication),
    )
    monkeypatch.setattr(
        coordinator_api_module,
        "control_plane_reservation_service",
        CoordinatorControlPlaneReservationService(publication=publication),
    )
    return repository


def test_coordinator_api_claim_renew_and_complete_publish_lease_history(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _install_in_memory_control_plane(monkeypatch)
    coordinator_api_module.store.reset([_card(state="OPEN")])

    claimed = _client().post("/cards/card-1/claim", json={"node_id": "worker-a", "lease_duration": 5.0})
    renewed = _client().post("/cards/card-1/renew", json={"node_id": "worker-a", "lease_duration": 7.0})
    completed = _client().post("/cards/card-1/complete", json={"node_id": "worker-a", "result": {"ok": True}})

    assert claimed.status_code == 200
    assert renewed.status_code == 200
    assert completed.status_code == 200
    assert claimed.json()["control_plane_reservation"]["reservation_kind"] == ReservationKind.RESOURCE.value
    assert claimed.json()["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert claimed.json()["control_plane_reservation"]["expiry_or_invalidation_basis"].startswith(
        "coordinator_claim_promoted_to_lease;"
    )
    assert claimed.json()["control_plane_reservation"]["supervisor_authority_ref"] == (
        "coordinator-api:claim:card-1:promote"
    )
    assert claimed.json()["control_plane_reservation"]["promotion_rule"] == "promote_on_non_hedged_claim_confirmation"
    assert claimed.json()["control_plane_lease"]["resource_id"] == "coordinator-card:card-1"
    assert claimed.json()["control_plane_lease"]["status"] == LeaseStatus.ACTIVE.value
    assert claimed.json()["control_plane_lease"]["expiry_basis"].startswith("coordinator_store_lease;")
    assert claimed.json()["control_plane_lease"]["cleanup_eligibility_rule"] == "coordinator_complete_or_fail"
    assert claimed.json()["control_plane_lease"]["granted_timestamp"] == (
        claimed.json()["control_plane_lease"]["publication_timestamp"]
    )
    assert claimed.json()["control_plane_lease"]["last_confirmed_observation"] == (
        "coordinator-card:card-1:attempts:1:node:worker-a:event:claim"
    )
    assert claimed.json()["control_plane_lease"]["source_reservation_id"] == "coordinator-reservation:card-1:lease_epoch:00000001"
    assert renewed.json()["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert renewed.json()["control_plane_lease"]["status"] == LeaseStatus.ACTIVE.value
    assert renewed.json()["control_plane_lease"]["granted_timestamp"] == claimed.json()["control_plane_lease"]["granted_timestamp"]
    assert renewed.json()["control_plane_lease"]["publication_timestamp"] != claimed.json()["control_plane_lease"]["publication_timestamp"]
    assert renewed.json()["control_plane_lease"]["last_confirmed_observation"] == (
        "coordinator-card:card-1:attempts:1:node:worker-a:event:renew"
    )
    assert completed.json()["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert completed.json()["control_plane_lease"]["status"] == LeaseStatus.RELEASED.value
    assert completed.json()["control_plane_lease"]["granted_timestamp"] == claimed.json()["control_plane_lease"]["granted_timestamp"]
    assert completed.json()["control_plane_lease"]["last_confirmed_observation"] == "coordinator-card:card-1:complete"

    leases = repository.leases_by_id["coordinator-lease:card-1"]
    assert [record.status for record in leases] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
    assert leases[0].holder_ref == "coordinator-node:worker-a"
    assert leases[1].lease_epoch == leases[0].lease_epoch
    assert leases[0].source_reservation_id == "coordinator-reservation:card-1:lease_epoch:00000001"
    assert leases[-1].expiry_basis == "coordinator_complete"
    reservations = repository.reservations_by_id["coordinator-reservation:card-1:lease_epoch:00000001"]
    assert [record.status for record in reservations] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]


def test_coordinator_api_claim_after_expiry_publishes_expired_then_active_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _install_in_memory_control_plane(monkeypatch)
    publication = coordinator_api_module.control_plane_publication
    coordinator_api_module.store.reset(
        [_card(state="CLAIMED", claimed_by="worker-a", lease_expires_at=time.monotonic() - 1.0)]
    )

    # Seed the prior active lease so expiry can close truthful history before the new claimant takes over.
    import asyncio

    asyncio.run(
        publication.publish_reservation(
            reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
            holder_ref="coordinator-node:worker-a",
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref="coordinator-card:card-1",
            creation_timestamp="2026-03-24T05:59:59+00:00",
            expiry_or_invalidation_basis="coordinator_claim_reserved;card=card-1;attempts=0;lease_expires_at_monotonic=stale",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref="coordinator-api:claim:card-1:reserve",
            promotion_rule="promote_on_non_hedged_claim_confirmation",
        )
    )
    asyncio.run(
        publication.promote_reservation_to_lease(
            reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
            promoted_lease_id="coordinator-lease:card-1",
            supervisor_authority_ref="coordinator-api:claim:card-1:promote",
            promotion_basis="coordinator_claim_promoted_to_lease;publication_timestamp=2026-03-24T06:00:00+00:00",
        )
    )

    asyncio.run(
        publication.publish_lease(
            lease_id="coordinator-lease:card-1",
            resource_id="coordinator-card:card-1",
            holder_ref="coordinator-node:worker-a",
            lease_epoch=1,
            publication_timestamp="2026-03-24T06:00:00+00:00",
            expiry_basis="coordinator_store_lease;lease_duration=1.000000;lease_expires_at_monotonic=stale",
            status=LeaseStatus.ACTIVE,
            granted_timestamp="2026-03-24T06:00:00+00:00",
            last_confirmed_observation="coordinator-card:card-1:attempts:0:node:worker-a:event:claim",
            cleanup_eligibility_rule="coordinator_complete_or_fail",
            source_reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
        )
    )

    claimed = _client().post("/cards/card-1/claim", json={"node_id": "worker-b", "lease_duration": 5.0})

    assert claimed.status_code == 200
    claimed_payload = claimed.json()
    assert claimed_payload["control_plane_reservation"]["reservation_kind"] == ReservationKind.RESOURCE.value
    assert claimed_payload["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert claimed_payload["control_plane_reservation"]["expiry_or_invalidation_basis"].startswith(
        "coordinator_claim_promoted_to_lease;"
    )
    assert claimed_payload["control_plane_reservation"]["supervisor_authority_ref"] == (
        "coordinator-api:claim:card-1:promote"
    )
    assert claimed_payload["control_plane_reservation"]["promotion_rule"] == "promote_on_non_hedged_claim_confirmation"
    assert claimed_payload["control_plane_lease"]["resource_id"] == "coordinator-card:card-1"
    assert claimed_payload["control_plane_lease"]["status"] == LeaseStatus.ACTIVE.value
    assert claimed_payload["control_plane_lease"]["expiry_basis"].startswith("coordinator_store_lease;")
    assert claimed_payload["control_plane_lease"]["cleanup_eligibility_rule"] == "coordinator_complete_or_fail"
    assert claimed_payload["control_plane_lease"]["granted_timestamp"] == claimed_payload["control_plane_lease"]["publication_timestamp"]
    assert claimed_payload["control_plane_lease"]["last_confirmed_observation"] == (
        "coordinator-card:card-1:attempts:1:node:worker-b:event:claim"
    )
    assert claimed_payload["control_plane_lease"]["source_reservation_id"] == "coordinator-reservation:card-1:lease_epoch:00000002"
    leases = repository.leases_by_id["coordinator-lease:card-1"]
    assert [record.status for record in leases] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.EXPIRED,
        LeaseStatus.ACTIVE,
    ]
    assert leases[1].holder_ref == "coordinator-node:worker-a"
    assert leases[2].holder_ref == "coordinator-node:worker-b"
    assert leases[2].lease_epoch == 2
    assert leases[2].source_reservation_id == "coordinator-reservation:card-1:lease_epoch:00000002"
    reservations = repository.reservations_by_id["coordinator-reservation:card-1:lease_epoch:00000002"]
    assert [record.status for record in reservations] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]


def test_coordinator_api_open_cards_publish_expired_lease_history(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _install_in_memory_control_plane(monkeypatch)
    publication = coordinator_api_module.control_plane_publication
    coordinator_api_module.store.reset(
        [_card(state="CLAIMED", claimed_by="worker-a", lease_expires_at=time.monotonic() - 1.0)]
    )

    import asyncio

    asyncio.run(
        publication.publish_reservation(
            reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
            holder_ref="coordinator-node:worker-a",
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref="coordinator-card:card-1",
            creation_timestamp="2026-03-24T05:59:59+00:00",
            expiry_or_invalidation_basis="coordinator_claim_reserved;card=card-1;attempts=0;lease_expires_at_monotonic=stale",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref="coordinator-api:claim:card-1:reserve",
            promotion_rule="promote_on_non_hedged_claim_confirmation",
        )
    )
    asyncio.run(
        publication.promote_reservation_to_lease(
            reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
            promoted_lease_id="coordinator-lease:card-1",
            supervisor_authority_ref="coordinator-api:claim:card-1:promote",
            promotion_basis="coordinator_claim_promoted_to_lease;publication_timestamp=2026-03-24T06:00:00+00:00",
        )
    )
    asyncio.run(
        publication.publish_lease(
            lease_id="coordinator-lease:card-1",
            resource_id="coordinator-card:card-1",
            holder_ref="coordinator-node:worker-a",
            lease_epoch=1,
            publication_timestamp="2026-03-24T06:00:00+00:00",
            expiry_basis="coordinator_store_lease;lease_duration=1.000000;lease_expires_at_monotonic=stale",
            status=LeaseStatus.ACTIVE,
            granted_timestamp="2026-03-24T06:00:00+00:00",
            last_confirmed_observation="coordinator-card:card-1:attempts:0:node:worker-a:event:claim",
            cleanup_eligibility_rule="coordinator_complete_or_fail",
            source_reservation_id="coordinator-reservation:card-1:lease_epoch:00000001",
        )
    )

    listed = _client().get("/cards", params={"state": "open"})

    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) == 1
    assert payload[0]["state"] == "OPEN"
    assert payload[0]["control_plane_reservation"]["reservation_kind"] == ReservationKind.RESOURCE.value
    assert payload[0]["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert payload[0]["control_plane_reservation"]["expiry_or_invalidation_basis"].startswith(
        "coordinator_claim_promoted_to_lease;"
    )
    assert payload[0]["control_plane_lease"]["resource_id"] == "coordinator-card:card-1"
    assert payload[0]["control_plane_lease"]["status"] == LeaseStatus.EXPIRED.value
    assert payload[0]["control_plane_lease"]["expiry_basis"].startswith("coordinator_store_")
    assert payload[0]["control_plane_lease"]["cleanup_eligibility_rule"] == "coordinator_complete_or_fail"
    assert payload[0]["control_plane_lease"]["granted_timestamp"] == "2026-03-24T06:00:00+00:00"
    assert payload[0]["control_plane_lease"]["publication_timestamp"] != "2026-03-24T06:00:00+00:00"
    assert payload[0]["control_plane_lease"]["last_confirmed_observation"] == (
        "coordinator-card:card-1:attempts:0:node:worker-a:event:expire"
    )
    leases = repository.leases_by_id["coordinator-lease:card-1"]
    assert [record.status for record in leases] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.EXPIRED,
    ]


def test_coordinator_api_fail_returns_release_state_control_plane_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _install_in_memory_control_plane(monkeypatch)
    coordinator_api_module.store.reset([_card(state="OPEN")])

    claimed = _client().post("/cards/card-1/claim", json={"node_id": "worker-a", "lease_duration": 5.0})
    failed = _client().post("/cards/card-1/fail", json={"node_id": "worker-a", "result": {"ok": False}})

    assert claimed.status_code == 200
    assert failed.status_code == 200
    failed_payload = failed.json()
    assert failed_payload["state"] == "FAILED"
    assert failed_payload["control_plane_reservation"]["reservation_kind"] == ReservationKind.RESOURCE.value
    assert failed_payload["control_plane_reservation"]["status"] == ReservationStatus.PROMOTED_TO_LEASE.value
    assert failed_payload["control_plane_reservation"]["supervisor_authority_ref"] == (
        "coordinator-api:claim:card-1:promote"
    )
    assert failed_payload["control_plane_lease"]["resource_id"] == "coordinator-card:card-1"
    assert failed_payload["control_plane_lease"]["status"] == LeaseStatus.RELEASED.value
    assert failed_payload["control_plane_lease"]["expiry_basis"] == "coordinator_fail"
    assert failed_payload["control_plane_lease"]["cleanup_eligibility_rule"] == "coordinator_complete_or_fail"
    assert failed_payload["control_plane_lease"]["granted_timestamp"] == claimed.json()["control_plane_lease"]["granted_timestamp"]
    assert failed_payload["control_plane_lease"]["last_confirmed_observation"] == "coordinator-card:card-1:fail"

    leases = repository.leases_by_id["coordinator-lease:card-1"]
    assert [record.status for record in leases] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]


def test_coordinator_api_claim_fail_closes_authority_on_promotion_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _install_in_memory_control_plane(monkeypatch)
    coordinator_api_module.store.reset([_card(state="OPEN")])

    async def _raise_promote_failure(**_kwargs):
        raise RuntimeError("promote failed")

    monkeypatch.setattr(
        coordinator_api_module.control_plane_publication,
        "promote_reservation_to_lease",
        _raise_promote_failure,
    )

    claimed = _client(raise_server_exceptions=False).post(
        "/cards/card-1/claim",
        json={"node_id": "worker-a", "lease_duration": 5.0},
    )

    assert claimed.status_code == 500
    assert claimed.text == "Internal Server Error"
    reservations = repository.reservations_by_id["coordinator-reservation:card-1:lease_epoch:00000001"]
    leases = repository.leases_by_id["coordinator-lease:card-1"]
    assert [record.status for record in reservations] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert reservations[-1].expiry_or_invalidation_basis == "coordinator_claim_promotion_failed;lease_epoch=00000001"
    assert [record.status for record in leases] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
    assert leases[-1].expiry_basis == "coordinator_claim_promotion_failed;lease_epoch=00000001"
