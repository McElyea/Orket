from __future__ import annotations

import pytest

from orket.application.services.companion_config_models import (
    CompanionModeConfig,
    CompanionRoleId,
    RelationshipStyleId,
)
from orket.application.services.config_precedence_resolver import ConfigPrecedenceResolver
from orket.application.services.mode_change_policy import ModeChangePolicy


def test_mode_change_policy_pending_scope_is_next_resolve_only() -> None:
    """Layer: integration. Verifies pending mode changes apply on next resolve and then clear."""
    resolver = ConfigPrecedenceResolver(extension_defaults={"mode": {"role_id": "researcher"}})
    policy = ModeChangePolicy()
    baseline = resolver.resolve()
    assert baseline.mode.role_id == CompanionRoleId.RESEARCHER

    policy.apply_mode_change(
        resolver=resolver,
        mode=CompanionModeConfig(
            role_id=CompanionRoleId.TUTOR,
            relationship_style=RelationshipStyleId.PLATONIC,
        ),
        scope="pending_next_turn",
    )

    next_turn = resolver.resolve()
    assert next_turn.mode.role_id == CompanionRoleId.TUTOR
    following_turn = resolver.resolve()
    assert following_turn.mode.role_id == CompanionRoleId.RESEARCHER


def test_mode_change_policy_session_scope_persists_until_clear_session() -> None:
    """Layer: integration. Verifies session-scoped mode changes remain active across resolves."""
    resolver = ConfigPrecedenceResolver(extension_defaults={"mode": {"role_id": "general_assistant"}})
    policy = ModeChangePolicy()
    policy.apply_mode_change(
        resolver=resolver,
        mode=CompanionModeConfig(
            role_id=CompanionRoleId.STRATEGIST,
            relationship_style=RelationshipStyleId.INTERMEDIATE,
        ),
        scope="session",
    )

    resolved = resolver.resolve()
    assert resolved.mode.role_id == CompanionRoleId.STRATEGIST
    assert resolved.mode.relationship_style == RelationshipStyleId.INTERMEDIATE

    resolved_again = resolver.resolve()
    assert resolved_again.mode.role_id == CompanionRoleId.STRATEGIST


def test_mode_change_policy_rejects_unknown_scope() -> None:
    """Layer: unit. Verifies unknown mode-change scopes fail closed."""
    resolver = ConfigPrecedenceResolver()
    policy = ModeChangePolicy()
    with pytest.raises(ValueError, match="E_COMPANION_MODE_SCOPE_INVALID"):
        policy.apply_mode_change(
            resolver=resolver,
            mode=CompanionModeConfig(),
            scope="invalid_scope",  # type: ignore[arg-type]
        )
