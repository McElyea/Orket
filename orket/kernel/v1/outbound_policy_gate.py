from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .nervous_system_leaks import sanitize_text

_DEFAULT_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "credential",
    "email",
    "password",
    "secret",
    "ssn",
    "token",
)
_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
)


@dataclass(frozen=True)
class OutboundPolicyGate:
    pii_field_paths: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    allowed_output_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    placeholder: str = "[REDACTED]"
    sensitive_key_tokens: tuple[str, ...] = _DEFAULT_SENSITIVE_KEY_TOKENS

    def filter(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        filtered, _report = self.filter_with_report(event_type, payload)
        return filtered

    def filter_with_report(self, event_type: str, payload: Any) -> tuple[Any, dict[str, Any]]:
        redacted_paths: list[str] = []
        compiled_patterns = tuple(re.compile(pattern) for pattern in self.forbidden_patterns)

        def _path_text(path: tuple[str, ...]) -> str:
            return ".".join(path)

        def _key_is_sensitive(key: str) -> bool:
            lowered = key.strip().lower()
            return any(token in lowered for token in self.sensitive_key_tokens)

        def _sanitize_string(value: str, path: tuple[str, ...]) -> str:
            sanitized = sanitize_text(value)
            for pattern in _PII_PATTERNS:
                sanitized = pattern.sub(self.placeholder, sanitized)
            for pattern in compiled_patterns:
                sanitized = pattern.sub(self.placeholder, sanitized)
            if sanitized != value:
                redacted_paths.append(_path_text(path))
            return sanitized

        def _scrub(value: Any, path: tuple[str, ...], current_event_type: str) -> Any:
            path_text = _path_text(path)
            if path_text and _path_is_configured(path, self.pii_field_paths):
                redacted_paths.append(path_text)
                return self.placeholder
            if isinstance(value, Mapping):
                child_event_type = _event_type_for_mapping(current_event_type, value)
                allowed = self.allowed_output_fields.get(child_event_type) if not path or "event_type" in value else None
                scrubbed: dict[str, Any] = {}
                for raw_key, raw_child in value.items():
                    key = str(raw_key)
                    if allowed is not None and key not in allowed:
                        continue
                    child_path = (*path, key)
                    if _key_is_sensitive(key) and not isinstance(raw_child, (Mapping, list, tuple)):
                        redacted_paths.append(_path_text(child_path))
                        scrubbed[key] = self.placeholder
                        continue
                    scrubbed[key] = _scrub(raw_child, child_path, child_event_type)
                return scrubbed
            if isinstance(value, list):
                return [_scrub(item, (*path, str(index)), current_event_type) for index, item in enumerate(value)]
            if isinstance(value, tuple):
                return tuple(_scrub(item, (*path, str(index)), current_event_type) for index, item in enumerate(value))
            if isinstance(value, str):
                return _sanitize_string(value, path)
            return value

        scrubbed_payload = _scrub(payload, (), str(event_type or ""))
        scrubbed_payload, ledger_report = _preserve_ledger_export_truth(payload, scrubbed_payload)
        report = {
            "applied": True,
            "redaction_count": len(redacted_paths),
            "redacted_paths": sorted(set(path for path in redacted_paths if path)),
            **ledger_report,
        }
        return scrubbed_payload, report


def load_outbound_policy_config_file(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_bytes().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("outbound policy config file must contain a JSON object")
    return dict(payload)


def load_outbound_policy_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return merge_outbound_policy_config(_environment_policy_config(os.environ), dict(config or {}))


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
                merged["pii_field_paths"] = _dedupe_tuple((*_string_tuple(merged.get("pii_field_paths")), *_string_tuple(value)))
            elif key == "forbidden_patterns":
                merged[key] = _dedupe_tuple((*_string_tuple(merged.get(key)), *_string_tuple(value)))
            else:
                merged[key] = value
    return merged


def apply_outbound_policy_gate(payload: Any, config: Mapping[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    gate_config = load_outbound_policy_config(config)
    event_type = _resolve_event_type(payload, gate_config)
    gate = OutboundPolicyGate(
        pii_field_paths=_string_tuple(gate_config.get("pii_field_paths")),
        forbidden_patterns=_string_tuple(gate_config.get("forbidden_patterns")),
        allowed_output_fields=_normalize_allowed_output_fields(gate_config.get("allowed_output_fields")),
        placeholder=str(gate_config.get("placeholder") or "[REDACTED]"),
        sensitive_key_tokens=tuple(
            str(token).strip().lower()
            for token in gate_config.get("sensitive_keys", _DEFAULT_SENSITIVE_KEY_TOKENS)
            if str(token).strip()
        ),
    )
    return gate.filter_with_report(event_type, payload)


def _environment_policy_config(environ: Mapping[str, str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if environ.get("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS"):
        config["pii_field_paths"] = _split_config_list(str(environ["ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS"]))
    if environ.get("ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS"):
        config["forbidden_patterns"] = _split_config_list(str(environ["ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS"]))
    if environ.get("ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS"):
        config["allowed_output_fields"] = json.loads(str(environ["ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS"]))
    return config


def _resolve_event_type(payload: Any, config: Mapping[str, Any]) -> str:
    for key in ("event_type", "surface"):
        if str(config.get(key) or "").strip():
            return str(config[key]).strip()
    if isinstance(payload, Mapping) and str(payload.get("event_type") or "").strip():
        return str(payload["event_type"]).strip()
    return "default"


def _event_type_for_mapping(current_event_type: str, value: Mapping[str, Any]) -> str:
    raw = value.get("event_type")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return current_event_type


def _path_is_configured(path: tuple[str, ...], configured_paths: tuple[str, ...]) -> bool:
    for configured in configured_paths:
        configured_parts = tuple(part for part in configured.split(".") if part)
        if len(configured_parts) != len(path):
            continue
        if all(configured_part == "*" or configured_part == actual for configured_part, actual in zip(configured_parts, path)):
            return True
    return False


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


def _preserve_ledger_export_truth(original: Any, scrubbed: Any) -> tuple[Any, dict[str, Any]]:
    if not _is_ledger_export(original) or not isinstance(scrubbed, dict):
        return scrubbed, {}
    original_events = [event for event in original.get("events", []) if isinstance(event, Mapping)]
    scrubbed_events = [event for event in scrubbed.get("events", []) if isinstance(event, Mapping)]
    redacted_positions = {
        int(original_event.get("position"))
        for original_event, scrubbed_event in zip(original_events, scrubbed_events)
        if dict(original_event) != dict(scrubbed_event)
    }
    if not redacted_positions:
        return scrubbed, {"ledger_redacted_event_positions": []}

    final_disclosed = [
        dict(event)
        for event in original_events
        if int(event.get("position")) not in redacted_positions
    ]
    canonical_count = int(original.get("canonical", {}).get("event_count") or len(original_events))
    transformed = dict(scrubbed)
    transformed["export_scope"] = "partial_view"
    transformed["events"] = final_disclosed
    transformed["omitted_spans"] = _ledger_omitted_spans(original, {int(event["position"]) for event in final_disclosed}, canonical_count)
    transformed["verification"] = {"result": "partial_valid", "meaning": "partial verified view"}
    summary = dict(transformed.get("summary") or {})
    if summary:
        summary["exported_event_count"] = len(final_disclosed)
        transformed["summary"] = summary
    policy_snapshot = dict(transformed.get("policy_snapshot") or {})
    if policy_snapshot:
        policy_snapshot["payload_bytes"] = "partial_disclosure"
        policy_snapshot["outbound_policy_gate"] = "redacted_to_partial_view"
        transformed["policy_snapshot"] = policy_snapshot
    return transformed, {"ledger_redacted_event_positions": sorted(redacted_positions)}


def _is_ledger_export(payload: Any) -> bool:
    return isinstance(payload, Mapping) and payload.get("schema_version") == "ledger_export.v1" and isinstance(payload.get("events"), list)


def _ledger_omitted_spans(original: Mapping[str, Any], disclosed_positions: set[int], canonical_count: int) -> list[dict[str, Any]]:
    chain_by_position: dict[int, str] = {}
    for event in original.get("events", []):
        if isinstance(event, Mapping):
            chain_by_position[int(event.get("position"))] = str(event.get("chain_hash") or "")
    for span in original.get("omitted_spans", []):
        if isinstance(span, Mapping):
            chain_by_position[int(span.get("to_position"))] = str(span.get("next_chain_hash") or "")
    ledger_hash = str((original.get("canonical") or {}).get("ledger_hash") or "")
    if canonical_count > 0:
        chain_by_position.setdefault(canonical_count, ledger_hash)

    spans: list[dict[str, Any]] = []
    position = 1
    while position <= canonical_count:
        if position in disclosed_positions:
            position += 1
            continue
        start = position
        while position <= canonical_count and position not in disclosed_positions:
            position += 1
        end = position - 1
        previous_chain_hash = "GENESIS" if start == 1 else chain_by_position.get(start - 1, "")
        spans.append(
            {
                "from_position": start,
                "to_position": end,
                "previous_chain_hash": previous_chain_hash,
                "next_chain_hash": chain_by_position.get(end, ledger_hash),
            }
        )
    return spans


__all__ = [
    "OutboundPolicyGate",
    "apply_outbound_policy_gate",
    "load_outbound_policy_config",
    "load_outbound_policy_config_file",
    "merge_outbound_policy_config",
]
