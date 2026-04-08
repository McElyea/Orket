from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .companion_config_models import CompanionConfig


def _clone_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_value(item) for item in value]
    return value


def _merge_values(base: Any, override: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged: dict[str, Any] = {str(key): _clone_value(value) for key, value in base.items()}
        for key, value in override.items():
            key_name = str(key)
            if key_name in merged:
                merged[key_name] = _merge_values(merged[key_name], value)
            else:
                merged[key_name] = _clone_value(value)
        return merged
    return _clone_value(override)


def _normalize_layer(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    normalized = _clone_value(payload)
    return normalized if isinstance(normalized, dict) else {}


class ConfigPrecedenceResolver:
    """
    Deterministic Companion config layering:
    extension_defaults < profile_defaults < session_overrides < pending_next_turn.
    """
    _DEFAULT_SECTION_KEYS: frozenset[str] = frozenset({"mode", "memory", "voice"})

    def __init__(
        self,
        *,
        extension_defaults: Mapping[str, Any] | None = None,
        profile_defaults: Mapping[str, Any] | None = None,
        extra_sections: set[str] | None = None,
    ) -> None:
        self._extension_defaults = _normalize_layer(extension_defaults)
        self._profile_defaults = _normalize_layer(profile_defaults)
        self._session_overrides: dict[str, Any] = {}
        self._pending_next_turn: dict[str, Any] = {}
        self._section_keys = set(self._DEFAULT_SECTION_KEYS)
        for section in set(extra_sections or set()):
            section_name = str(section or "").strip()
            if not section_name:
                raise ValueError("E_COMPANION_CONFIG_SECTION_INVALID: section=''")
            self._section_keys.add(section_name)

    @property
    def section_keys(self) -> frozenset[str]:
        return frozenset(self._section_keys)

    def set_extension_defaults(self, payload: Mapping[str, Any] | None) -> None:
        self._extension_defaults = _normalize_layer(payload)

    def set_profile_defaults(self, payload: Mapping[str, Any] | None) -> None:
        self._profile_defaults = _normalize_layer(payload)

    def set_session_override(self, section: str, value: Any) -> None:
        self._set_layer_value(self._session_overrides, section=section, value=value)

    def set_pending_next_turn(self, section: str, value: Any) -> None:
        self._set_layer_value(self._pending_next_turn, section=section, value=value)

    def clear_session(self) -> None:
        self._session_overrides = {}
        self._pending_next_turn = {}

    def preview(self, *, include_pending_next_turn: bool = True) -> CompanionConfig:
        merged = self._merged_payload(include_pending_next_turn=include_pending_next_turn)
        return CompanionConfig.model_validate(merged)

    def resolve(self) -> CompanionConfig:
        resolved = self.preview(include_pending_next_turn=True)
        self._pending_next_turn = {}
        return resolved

    def _set_layer_value(self, layer: dict[str, Any], *, section: str, value: Any) -> None:
        section_name = str(section or "").strip()
        if section_name not in self._section_keys:
            allowed = ", ".join(sorted(self._section_keys))
            raise ValueError(f"E_COMPANION_CONFIG_SECTION_INVALID: section='{section_name}' allowed='{allowed}'")
        existing = layer.get(section_name)
        if existing is None:
            layer[section_name] = _clone_value(value)
            return
        layer[section_name] = _merge_values(existing, value)

    def _merged_payload(self, *, include_pending_next_turn: bool) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        layers: list[dict[str, Any]] = [
            self._extension_defaults,
            self._profile_defaults,
            self._session_overrides,
        ]
        if include_pending_next_turn:
            layers.append(self._pending_next_turn)
        for layer in layers:
            merged = _merge_values(merged, layer)
        return merged
