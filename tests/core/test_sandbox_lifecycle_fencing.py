# Layer: unit

from __future__ import annotations

import pytest

from orket.core.domain.sandbox_lifecycle import (
    CleanupState,
    SandboxLifecycleError,
    assert_cleanup_claim,
    assert_lifecycle_fence,
)


def test_lifecycle_fence_accepts_matching_owner_epoch_and_version() -> None:
    assert (
        assert_lifecycle_fence(
            expected_owner_instance_id="owner-a",
            actual_owner_instance_id="owner-a",
            expected_lease_epoch=4,
            actual_lease_epoch=4,
            expected_record_version=12,
            actual_record_version=12,
        )
        is True
    )


def test_lifecycle_fence_rejects_stale_owner() -> None:
    with pytest.raises(SandboxLifecycleError, match="Stale owner"):
        assert_lifecycle_fence(
            expected_owner_instance_id="owner-a",
            actual_owner_instance_id="owner-b",
            expected_lease_epoch=4,
            actual_lease_epoch=4,
            expected_record_version=12,
            actual_record_version=12,
        )


def test_lifecycle_fence_rejects_lease_epoch_mismatch() -> None:
    with pytest.raises(SandboxLifecycleError, match="Lease epoch mismatch"):
        assert_lifecycle_fence(
            expected_owner_instance_id="owner-a",
            actual_owner_instance_id="owner-a",
            expected_lease_epoch=4,
            actual_lease_epoch=5,
            expected_record_version=12,
            actual_record_version=12,
        )


def test_lifecycle_fence_rejects_record_version_mismatch() -> None:
    with pytest.raises(SandboxLifecycleError, match="Record version mismatch"):
        assert_lifecycle_fence(
            expected_owner_instance_id="owner-a",
            actual_owner_instance_id="owner-a",
            expected_lease_epoch=4,
            actual_lease_epoch=4,
            expected_record_version=12,
            actual_record_version=13,
        )


def test_cleanup_claim_accepts_unowned_scheduled_record() -> None:
    assert (
        assert_cleanup_claim(
            current_cleanup_state=CleanupState.SCHEDULED,
            claimant_id="sweeper-a",
            existing_cleanup_owner=None,
            expected_record_version=9,
            actual_record_version=9,
        )
        is True
    )


def test_cleanup_claim_rejects_non_scheduled_state() -> None:
    with pytest.raises(SandboxLifecycleError, match="requires scheduled cleanup state"):
        assert_cleanup_claim(
            current_cleanup_state=CleanupState.IN_PROGRESS,
            claimant_id="sweeper-a",
            existing_cleanup_owner=None,
            expected_record_version=9,
            actual_record_version=9,
        )


def test_cleanup_claim_rejects_competing_owner() -> None:
    with pytest.raises(SandboxLifecycleError, match="owned by another actor"):
        assert_cleanup_claim(
            current_cleanup_state=CleanupState.SCHEDULED,
            claimant_id="sweeper-a",
            existing_cleanup_owner="sweeper-b",
            expected_record_version=9,
            actual_record_version=9,
        )


def test_cleanup_claim_rejects_record_version_mismatch() -> None:
    with pytest.raises(SandboxLifecycleError, match="record version mismatch"):
        assert_cleanup_claim(
            current_cleanup_state=CleanupState.SCHEDULED,
            claimant_id="sweeper-a",
            existing_cleanup_owner=None,
            expected_record_version=9,
            actual_record_version=10,
        )
