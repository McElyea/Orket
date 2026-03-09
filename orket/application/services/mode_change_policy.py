from __future__ import annotations

from typing import Literal

from .companion_config_models import CompanionModeConfig
from .config_precedence_resolver import ConfigPrecedenceResolver

ModeChangeScope = Literal["session", "pending_next_turn"]


class ModeChangePolicy:
    """Applies Companion mode changes with explicit timing scope."""

    @staticmethod
    def apply_mode_change(
        *,
        resolver: ConfigPrecedenceResolver,
        mode: CompanionModeConfig,
        scope: ModeChangeScope,
    ) -> None:
        payload = mode.model_dump(mode="json", exclude_none=True)
        if scope == "session":
            resolver.set_session_override("mode", payload)
            return
        if scope == "pending_next_turn":
            resolver.set_pending_next_turn("mode", payload)
            return
        raise ValueError(f"E_COMPANION_MODE_SCOPE_INVALID: {scope}")
