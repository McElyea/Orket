"""Captured configuration shared by application-owned runtime construction."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.settings import load_user_preferences, load_user_settings, set_runtime_settings_context


@dataclass(frozen=True)
class RuntimeConstructionInputs:
    invocation_root: Path
    environment: Mapping[str, str] = field(repr=False)
    user_settings_json: str = field(repr=False)
    user_preferences_json: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.invocation_root.is_absolute():
            raise ValueError("E_RUNTIME_CONSTRUCTION_ROOT_ABSOLUTE_REQUIRED")
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))

    @classmethod
    def capture(cls, *, environment: Mapping[str, str] | None = None) -> RuntimeConstructionInputs:
        root = Path.cwd()
        observed = dict(os.environ if environment is None else environment)
        # The settings boundary permits pre-loop bootstrap or an explicitly bound snapshot.
        # It fails before filesystem reads when called unbound on an event-loop thread.
        settings, preferences = load_user_settings(), load_user_preferences()
        return cls(root, observed, json.dumps(settings, allow_nan=False), json.dumps(preferences, allow_nan=False))

    def user_settings(self) -> dict[str, Any]:
        return json.loads(self.user_settings_json)

    def user_preferences(self) -> dict[str, Any]:
        return json.loads(self.user_preferences_json)

    def bind_settings(self) -> None:
        """Bind only the calling execution context; never mutate process environment."""
        set_runtime_settings_context(user_settings=self.user_settings(), user_preferences=self.user_preferences(),
                                     environment=self.environment)
