from __future__ import annotations

import pytest

from orket.services.profile_write_policy import ProfileWritePolicy, ProfileWritePolicyError


def test_profile_write_policy_accepts_allowed_prefixes() -> None:
    """Layer: unit. Verifies allowed profile-memory key prefixes pass validation."""
    policy = ProfileWritePolicy()
    policy.validate(key="companion_setting.role_id", metadata={})
    policy.validate(key="companion_mode.relationship_style", metadata={})
    policy.validate(key="user_preference.voice_enabled", metadata={})


def test_profile_write_policy_rejects_forbidden_prefix() -> None:
    """Layer: unit. Verifies unknown profile-memory key prefixes are rejected."""
    policy = ProfileWritePolicy()
    with pytest.raises(ProfileWritePolicyError, match="E_PROFILE_MEMORY_KEY_FORBIDDEN"):
        policy.validate(key="arbitrary.note", metadata={})


def test_profile_write_policy_requires_confirmation_for_user_facts() -> None:
    """Layer: unit. Verifies user-fact writes require explicit user confirmation metadata."""
    policy = ProfileWritePolicy()
    with pytest.raises(ProfileWritePolicyError, match="E_PROFILE_MEMORY_CONFIRMATION_REQUIRED"):
        policy.validate(key="user_fact.name", metadata={})


def test_profile_write_policy_accepts_confirmed_user_facts() -> None:
    """Layer: unit. Verifies confirmed user-fact writes are allowed."""
    policy = ProfileWritePolicy()
    policy.validate(key="user_fact.name", metadata={"user_confirmed": True})
