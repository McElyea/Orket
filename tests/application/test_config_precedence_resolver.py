from __future__ import annotations

import pytest

from orket.application.services.companion_config_models import CompanionRoleId, RelationshipStyleId
from orket.application.services.config_precedence_resolver import ConfigPrecedenceResolver


def test_config_precedence_order_and_pending_consumption() -> None:
    """Layer: integration. Verifies precedence order and one-shot pending-next-turn consumption."""
    resolver = ConfigPrecedenceResolver(
        extension_defaults={"mode": {"role_id": "researcher", "relationship_style": "platonic"}},
        profile_defaults={
            "mode": {"role_id": "programmer", "relationship_style": "intermediate"},
            "memory": {"profile_memory_enabled": False},
        },
    )
    resolver.set_session_override("mode", {"relationship_style": "romantic"})
    resolver.set_pending_next_turn("mode", {"role_id": "tutor"})

    first = resolver.resolve()
    assert first.mode.role_id == CompanionRoleId.TUTOR
    assert first.mode.relationship_style == RelationshipStyleId.ROMANTIC
    assert first.memory.profile_memory_enabled is False

    second = resolver.resolve()
    assert second.mode.role_id == CompanionRoleId.PROGRAMMER
    assert second.mode.relationship_style == RelationshipStyleId.ROMANTIC


def test_config_precedence_recursive_merge_and_list_replacement() -> None:
    """Layer: integration. Verifies dict keys merge recursively and list values are replaced, not appended."""
    resolver = ConfigPrecedenceResolver(
        extension_defaults={
            "mode": {
                "relationship_style": "custom",
                "custom_style": {
                    "tones": ["warm", "curious"],
                    "limits": {"verbosity": "high", "safety": "strict"},
                },
            }
        },
        profile_defaults={
            "mode": {
                "custom_style": {
                    "tones": ["direct"],
                    "limits": {"verbosity": "medium"},
                }
            }
        },
    )

    resolved = resolver.resolve()
    custom_style = resolved.mode.custom_style or {}
    limits = custom_style.get("limits") or {}
    assert custom_style.get("tones") == ["direct"]
    assert limits == {"verbosity": "medium", "safety": "strict"}


def test_config_precedence_clear_session_resets_session_and_pending_layers() -> None:
    """Layer: integration. Verifies `clear_session()` drops session overrides and pending-next-turn state."""
    resolver = ConfigPrecedenceResolver(extension_defaults={"mode": {"role_id": "general_assistant"}})
    resolver.set_session_override("mode", {"role_id": "strategist"})
    resolver.set_pending_next_turn("mode", {"role_id": "tutor"})
    resolver.clear_session()

    resolved = resolver.resolve()
    assert resolved.mode.role_id == CompanionRoleId.GENERAL_ASSISTANT


def test_config_precedence_rejects_unknown_section() -> None:
    """Layer: unit. Verifies invalid section updates fail closed."""
    resolver = ConfigPrecedenceResolver()
    with pytest.raises(ValueError, match="E_COMPANION_CONFIG_SECTION_INVALID"):
        resolver.set_session_override("invalid_section", {"value": 1})


def test_config_precedence_accepts_registered_extension_section() -> None:
    """Layer: unit. Verifies extension-declared config sections can be layered."""
    resolver = ConfigPrecedenceResolver(
        extension_defaults={"appearance": {"theme": "dark"}},
        extra_sections={"appearance"},
    )
    resolver.set_session_override("appearance", {"accent": "blue"})

    resolved = resolver.resolve()

    assert resolved.model_extra is not None
    assert resolved.model_extra["appearance"] == {"theme": "dark", "accent": "blue"}
    assert "appearance" in resolver.section_keys


def test_config_precedence_preview_does_not_consume_pending_layer() -> None:
    """Layer: unit. Verifies preview reads pending-next-turn config without consuming it."""
    resolver = ConfigPrecedenceResolver(extension_defaults={"mode": {"role_id": "researcher"}})
    resolver.set_pending_next_turn("mode", {"role_id": "tutor"})

    preview = resolver.preview()
    assert preview.mode.role_id == CompanionRoleId.TUTOR

    resolved = resolver.resolve()
    assert resolved.mode.role_id == CompanionRoleId.TUTOR

    after = resolver.resolve()
    assert after.mode.role_id == CompanionRoleId.RESEARCHER
