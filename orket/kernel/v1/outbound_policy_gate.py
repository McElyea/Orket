from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from orket.application.services.outbound_policy_input_service import (
    capture_outbound_policy_inputs,
    load_outbound_policy_config,
    load_outbound_policy_config_file,
)
from orket.core.contracts.outbound_policy import (
    DEFAULT_SENSITIVE_KEY_TOKENS,
    OutboundPolicyInputs,
    merge_outbound_policy_config,
)

from .nervous_system_leaks import sanitize_text

_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
)


@dataclass(frozen=True)
class OutboundPolicyGate:
    pii_field_paths: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    allowed_output_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    placeholder: str = "[REDACTED]"
    sensitive_key_tokens: tuple[str, ...] = DEFAULT_SENSITIVE_KEY_TOKENS

    def __post_init__(self) -> None:
        inputs = OutboundPolicyInputs(self.pii_field_paths, self.forbidden_patterns,
            self.allowed_output_fields, self.placeholder, self.sensitive_key_tokens)
        for name in ("pii_field_paths", "forbidden_patterns", "allowed_output_fields", "placeholder", "sensitive_key_tokens"):
            object.__setattr__(self, name, getattr(inputs, name))

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


def apply_outbound_policy_gate(payload: Any, config: Mapping[str, Any] | None = None, *,
                               policy_inputs: OutboundPolicyInputs | None = None) -> tuple[Any, dict[str, Any]]:
    if policy_inputs is None:
        inputs = capture_outbound_policy_inputs(config)
    else:
        if not isinstance(policy_inputs, OutboundPolicyInputs):
            raise TypeError("E_OUTBOUND_POLICY_INPUTS_REQUIRED")
        inputs = (OutboundPolicyInputs.from_config(merge_outbound_policy_config(policy_inputs.to_config(), config))
                  if config else policy_inputs)
    event_type = _resolve_event_type(payload, inputs.to_config())
    gate = OutboundPolicyGate(inputs.pii_field_paths, inputs.forbidden_patterns, inputs.allowed_output_fields,
        inputs.placeholder, inputs.sensitive_key_tokens)
    return gate.filter_with_report(event_type, payload)


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
        if all(configured_part == "*" or configured_part == actual for configured_part, actual in zip(configured_parts, path, strict=True)):
            return True
    return False


def _preserve_ledger_export_truth(original: Any, scrubbed: Any) -> tuple[Any, dict[str, Any]]:
    if not _is_ledger_export(original) or not isinstance(scrubbed, dict):
        return scrubbed, {}
    original_events = [event for event in original.get("events", []) if isinstance(event, Mapping)]
    scrubbed_events = [event for event in scrubbed.get("events", []) if isinstance(event, Mapping)]
    redacted_positions = {
        int(original_event.get("position"))
        for original_event, scrubbed_event in zip(original_events, scrubbed_events, strict=False)
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
