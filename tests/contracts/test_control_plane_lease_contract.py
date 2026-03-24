# Layer: contract

from __future__ import annotations

import pytest

from orket.core.domain import LeaseStatus, build_lease_record


pytestmark = pytest.mark.contract


def test_build_lease_record_preserves_granted_timestamp_across_same_epoch_publications() -> None:
    first = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )

    second = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:01:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:06:00+00:00",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
        previous_record=first,
    )

    assert second.granted_timestamp == first.granted_timestamp
    assert second.history_refs


def test_build_lease_record_rejects_non_monotonic_publication_timestamp() -> None:
    first = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )

    with pytest.raises(ValueError, match="requires a newer publication_timestamp"):
        build_lease_record(
            lease_id="sandbox-lease:sb-1",
            resource_id="sandbox-scope:sb-1",
            holder_ref="sandbox-instance:runner-a",
            lease_epoch=1,
            publication_timestamp="2026-03-23T01:00:00+00:00",
            expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:06:00+00:00",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
            previous_record=first,
        )


def test_build_lease_record_allows_terminal_status_transition_within_same_epoch() -> None:
    first = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )

    expired = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:10:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.EXPIRED,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
        previous_record=first,
    )

    assert expired.status is LeaseStatus.EXPIRED


def test_build_lease_record_allows_pending_to_active_publication_with_same_timestamp() -> None:
    pending = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.PENDING,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )

    active = build_lease_record(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
        previous_record=pending,
    )

    assert active.status is LeaseStatus.ACTIVE
