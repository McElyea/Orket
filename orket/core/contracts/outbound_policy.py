"""Pure immutable outbound policy values; no environment, filesystem or owner lookup."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

DEFAULT_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "credential",
    "email",
    "password",
    "secret",
    "ssn",
    "token",
)


@dataclass(frozen=True, slots=True)
class OutboundPolicyInputs:
    pii_field_paths: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    allowed_output_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    placeholder: str = "[REDACTED]"
    sensitive_key_tokens: tuple[str, ...] = DEFAULT_SENSITIVE_KEY_TOKENS
    event_type: str = ""
    surface: str = ""

    def __post_init__(self) -> None:
        for name in ("pii_field_paths", "forbidden_patterns", "sensitive_key_tokens"):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)) or any(type(item) is not str for item in value):
                raise TypeError("E_OUTBOUND_POLICY_STRING_SEQUENCE_REQUIRED")
            object.__setattr__(self, name, tuple(value))
        fields = self.allowed_output_fields
        if not isinstance(fields, Mapping) or any(type(key) is not str for key in fields):
            raise TypeError("E_OUTBOUND_POLICY_FIELD_MAPPING_REQUIRED")
        detached = {}
        for key, values in fields.items():
            if not isinstance(values, (tuple, list)) or any(type(item) is not str for item in values):
                raise TypeError("E_OUTBOUND_POLICY_STRING_SEQUENCE_REQUIRED")
            detached[key] = tuple(values)
        object.__setattr__(self, "allowed_output_fields", MappingProxyType(detached))
        if any(type(getattr(self, name)) is not str for name in ("placeholder", "event_type", "surface")):
            raise TypeError("E_OUTBOUND_POLICY_STRING_REQUIRED")
        try:
            for pattern in self.forbidden_patterns:
                re.compile(pattern)
        except re.error as exc:
            raise ValueError("E_OUTBOUND_POLICY_INVALID_PATTERN") from exc

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> OutboundPolicyInputs:
        merged = merge_outbound_policy_config(config)
        return cls(
            pii_field_paths=_string_tuple(merged.get("pii_field_paths")),
            forbidden_patterns=_string_tuple(merged.get("forbidden_patterns")),
            allowed_output_fields=_normalize_allowed_output_fields(merged.get("allowed_output_fields")),
            placeholder=str(merged.get("placeholder") or "[REDACTED]"),
            sensitive_key_tokens=tuple(
                str(token).strip().lower()
                for token in merged.get("sensitive_keys", DEFAULT_SENSITIVE_KEY_TOKENS)
                if str(token).strip()
            ),
            event_type=str(merged.get("event_type") or "").strip(),
            surface=str(merged.get("surface") or "").strip(),
        )

    def to_config(self) -> dict[str, Any]:
        return dict(
            pii_field_paths=self.pii_field_paths,
            forbidden_patterns=self.forbidden_patterns,
            allowed_output_fields=dict(self.allowed_output_fields),
            placeholder=self.placeholder,
            sensitive_keys=self.sensitive_key_tokens,
            event_type=self.event_type,
            surface=self.surface,
        )


def merge_outbound_policy_config(*configs: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for config in configs:
        if not config:
            continue
        for key, value in dict(config).items():
            if key == "allowed_output_fields":
                current = dict(merged.get(key) or {})
                current.update(_normalize_allowed_output_fields(value))
                merged[key] = current
            elif key in {"pii_field_paths", "redact_paths"}:
                merged["pii_field_paths"] = _dedupe_tuple(
                    (*_string_tuple(merged.get("pii_field_paths")), *_string_tuple(value))
                )
            elif key == "forbidden_patterns":
                merged[key] = _dedupe_tuple((*_string_tuple(merged.get(key)), *_string_tuple(value)))
            else:
                merged[key] = value
    return merged


def environment_policy_config(environ: Mapping[str, str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if environ.get("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS"):
        config["pii_field_paths"] = _split_config_list(str(environ["ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS"]))
    if environ.get("ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS"):
        config["forbidden_patterns"] = _split_config_list(str(environ["ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS"]))
    if environ.get("ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS"):
        config["allowed_output_fields"] = json.loads(str(environ["ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS"]))
    return config


def _split_config_list(raw: str) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return ()
    if text.startswith("["):
        payload = json.loads(text)
        return _string_tuple(payload)
    return _dedupe_tuple(tuple(item.strip() for item in re.split(r"[\n,]", text) if item.strip()))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return tuple(str(item).strip() for item in value.values() if str(item).strip())
    try:
        return tuple(str(item).strip() for item in value if str(item).strip())
    except TypeError:
        return (str(value).strip(),) if str(value).strip() else ()


def _dedupe_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _normalize_allowed_output_fields(value: Any) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("allowed_output_fields must be an object")
    return {
        str(event_type).strip(): _string_tuple(fields)
        for event_type, fields in value.items()
        if str(event_type).strip()
    }
