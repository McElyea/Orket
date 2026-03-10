from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.application.services.companion_config_models import CompanionConfig


def test_companion_config_requires_custom_style_payload_for_custom_mode() -> None:
    """Layer: contract. Verifies custom relationship style requires explicit `custom_style` payload."""
    with pytest.raises(ValidationError, match="E_COMPANION_CUSTOM_STYLE_REQUIRED"):
        CompanionConfig.model_validate(
            {
                "mode": {
                    "role_id": "researcher",
                    "relationship_style": "custom",
                }
            }
        )


def test_companion_config_rejects_custom_style_payload_for_non_custom_mode() -> None:
    """Layer: contract. Verifies `custom_style` is rejected when relationship style is not `custom`."""
    with pytest.raises(ValidationError, match="E_COMPANION_CUSTOM_STYLE_FORBIDDEN"):
        CompanionConfig.model_validate(
            {
                "mode": {
                    "role_id": "researcher",
                    "relationship_style": "platonic",
                    "custom_style": {"tone": "calm"},
                }
            }
        )


def test_companion_config_clamps_voice_silence_delay_within_bounds() -> None:
    """Layer: contract. Verifies voice silence delay is host-clamped to configured bounds."""
    parsed = CompanionConfig.model_validate(
        {
            "voice": {
                "enabled": True,
                "silence_delay_sec": 99.0,
                "silence_delay_min_sec": 0.5,
                "silence_delay_max_sec": 6.0,
            }
        }
    )
    assert parsed.voice.silence_delay_sec == 6.0
    assert parsed.voice.adaptive_cadence_min_sec == 0.5
    assert parsed.voice.adaptive_cadence_max_sec == 4.0


def test_companion_config_rejects_invalid_adaptive_cadence_bounds() -> None:
    """Layer: contract. Verifies adaptive cadence bounds fail closed when max is lower than min."""
    with pytest.raises(ValidationError, match="E_COMPANION_ADAPTIVE_BOUNDS_INVALID"):
        CompanionConfig.model_validate(
            {
                "voice": {
                    "adaptive_cadence_min_sec": 2.0,
                    "adaptive_cadence_max_sec": 1.0,
                }
            }
        )


def test_companion_config_rejects_unknown_fields() -> None:
    """Layer: contract. Verifies schema forbids unknown config keys."""
    with pytest.raises(ValidationError):
        CompanionConfig.model_validate(
            {
                "mode": {"role_id": "tutor", "relationship_style": "platonic", "unexpected_key": True},
            }
        )


def test_companion_config_accepts_episodic_memory_toggle() -> None:
    """Layer: contract. Verifies episodic-memory toggle is accepted in the memory schema."""
    parsed = CompanionConfig.model_validate({"memory": {"episodic_memory_enabled": True}})
    assert parsed.memory.episodic_memory_enabled is True


def test_companion_config_accepts_extended_companion_roles() -> None:
    """Layer: contract. Verifies expanded companion-focused role IDs validate successfully."""
    parsed = CompanionConfig.model_validate({"mode": {"role_id": "girlfriend", "relationship_style": "romantic"}})
    assert parsed.mode.role_id.value == "girlfriend"
