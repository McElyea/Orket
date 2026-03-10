from __future__ import annotations

from orket.runtime.deterministic_mode_contract import (
    deterministic_mode_contract_snapshot,
    resolve_deterministic_mode_flag,
)


# Layer: unit
def test_resolve_deterministic_mode_flag_defaults_to_false() -> None:
    enabled, source = resolve_deterministic_mode_flag(environment={})
    assert enabled is False
    assert source == "default"


# Layer: contract
def test_resolve_deterministic_mode_flag_prefers_primary_env_key() -> None:
    enabled, source = resolve_deterministic_mode_flag(
        environment={
            "ORKET_DETERMINISTIC_MODE": "true",
            "ORKET_PROTOCOL_DETERMINISTIC_MODE": "false",
        }
    )
    assert enabled is True
    assert source == "ORKET_DETERMINISTIC_MODE"


# Layer: contract
def test_deterministic_mode_contract_snapshot_reflects_enabled_behavior() -> None:
    payload = deterministic_mode_contract_snapshot(
        environment={"ORKET_PROTOCOL_DETERMINISTIC_MODE": "1"}
    )
    assert payload["schema_version"] == "1.0"
    assert payload["deterministic_mode_enabled"] is True
    assert payload["resolution_source"] == "ORKET_PROTOCOL_DETERMINISTIC_MODE"
    assert payload["behavior_contract"]["optional_heuristics"] == "disabled"
