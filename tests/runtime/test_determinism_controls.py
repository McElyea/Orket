from __future__ import annotations

import pytest

from orket.runtime.determinism_controls import (
    build_determinism_controls,
    parse_env_allowlist,
    parse_network_allowlist,
    resolve_clock_artifact_ref,
    resolve_clock_mode,
    resolve_env_allowlist,
    resolve_locale,
    resolve_network_allowlist,
    resolve_network_mode,
    resolve_timezone,
    snapshot_env_allowlist,
)


def test_resolve_timezone_defaults_to_utc() -> None:
    assert resolve_timezone("", None) == "UTC"


def test_resolve_timezone_prefers_first_non_empty() -> None:
    assert resolve_timezone("", "America/Denver", "UTC") == "America/Denver"


def test_resolve_locale_defaults_to_c_utf8() -> None:
    assert resolve_locale("", None) == "C.UTF-8"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("off", "off"),
        ("offline", "off"),
        ("disabled", "off"),
        ("allowlist", "allowlist"),
        ("allow-list", "allowlist"),
        ("online_allowlist", "allowlist"),
    ],
)
def test_resolve_network_mode_aliases(raw: str, expected: str) -> None:
    assert resolve_network_mode(raw) == expected


def test_resolve_network_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError) as exc:
        resolve_network_mode("internet")
    assert "E_NETWORK_MODE_INVALID" in str(exc.value)


def test_parse_env_allowlist_accepts_csv_and_dedupes() -> None:
    assert parse_env_allowlist("PATH, HOME,PATH") == ["HOME", "PATH"]


def test_parse_env_allowlist_accepts_list() -> None:
    assert parse_env_allowlist(["A", "B", "A"]) == ["A", "B"]


def test_parse_network_allowlist_accepts_csv_and_dedupes() -> None:
    assert parse_network_allowlist("api.example.com, api.example.com,cache.example.com") == [
        "api.example.com",
        "cache.example.com",
    ]


def test_resolve_network_allowlist_chooses_first_non_empty_source() -> None:
    assert resolve_network_allowlist("", ["api.example.com"], "cache.example.com") == ["api.example.com"]


def test_resolve_clock_mode_aliases() -> None:
    assert resolve_clock_mode("wall-clock") == "wall"
    assert resolve_clock_mode("artifact") == "artifact_replay"


def test_resolve_clock_artifact_ref_prefers_first_non_empty() -> None:
    assert resolve_clock_artifact_ref("", "artifacts/clock/run-a.json", "fallback.json") == "artifacts/clock/run-a.json"


def test_resolve_env_allowlist_chooses_first_non_empty_source() -> None:
    assert resolve_env_allowlist("", ["A"], "B,C") == ["A"]


def test_snapshot_env_allowlist_uses_selected_keys_only() -> None:
    snapshot = snapshot_env_allowlist(
        allowlist=["HOME", "PATH", "MISSING"],
        environment={"PATH": "/bin", "HOME": "/home/user", "SECRET": "x"},
    )
    assert snapshot == {"HOME": "/home/user", "PATH": "/bin"}


def test_build_determinism_controls_contains_stable_hash() -> None:
    first = build_determinism_controls(
        timezone="UTC",
        locale="C.UTF-8",
        network_mode="allowlist",
        network_allowlist="api.example.com,cache.example.com",
        clock_mode="artifact",
        clock_artifact_ref="artifacts/clock/run-a.json",
        env_allowlist="HOME,PATH",
        environment={"HOME": "/home/user", "PATH": "/bin"},
    )
    second = build_determinism_controls(
        timezone="UTC",
        locale="C.UTF-8",
        network_mode="allow-list",
        network_allowlist=["cache.example.com", "api.example.com"],
        clock_mode="artifact_replay",
        clock_artifact_ref="artifacts/clock/run-a.json",
        env_allowlist=["PATH", "HOME"],
        environment={"PATH": "/bin", "HOME": "/home/user"},
    )
    assert first["env_allowlist_hash"] == second["env_allowlist_hash"]
    assert first["env_snapshot"] == second["env_snapshot"]
    assert first["network_allowlist_hash"] == second["network_allowlist_hash"]
    assert first["clock_artifact_hash"] == second["clock_artifact_hash"]


def test_build_determinism_controls_hash_changes_when_value_changes() -> None:
    first = build_determinism_controls(
        env_allowlist="HOME",
        environment={"HOME": "/home/one"},
    )
    second = build_determinism_controls(
        env_allowlist="HOME",
        environment={"HOME": "/home/two"},
    )
    assert first["env_allowlist_hash"] != second["env_allowlist_hash"]


def test_build_determinism_controls_clock_hash_changes_when_artifact_changes() -> None:
    first = build_determinism_controls(clock_artifact_ref="artifacts/clock/a.json")
    second = build_determinism_controls(clock_artifact_ref="artifacts/clock/b.json")
    assert first["clock_artifact_hash"] != second["clock_artifact_hash"]
