from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.interfaces.server_launcher import LauncherConfigError
from orket.interfaces.server_launcher import resolve_api_launch_settings


def _write_config(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_api_launch_settings_defaults_are_safe() -> None:
    settings = resolve_api_launch_settings(
        cli_host=None,
        cli_port=None,
        cli_profile=None,
        cli_reload=None,
        config_path=None,
        environ={},
    )
    assert settings.host == "127.0.0.1"
    assert settings.port == 8082
    assert settings.profile == "safe"
    assert settings.reload is False


def test_resolve_api_launch_settings_applies_env_when_no_higher_precedence() -> None:
    settings = resolve_api_launch_settings(
        cli_host=None,
        cli_port=None,
        cli_profile=None,
        cli_reload=None,
        config_path=None,
        environ={"ORKET_HOST": "127.0.0.9", "ORKET_PORT": "8091"},
    )
    assert settings.host == "127.0.0.9"
    assert settings.port == 8091


def test_resolve_api_launch_settings_precedence_cli_over_config_over_env(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher.json"
    _write_config(config_path, {"host": "127.0.0.7", "port": 8093})
    settings = resolve_api_launch_settings(
        cli_host="127.0.0.5",
        cli_port=8095,
        cli_profile=None,
        cli_reload=None,
        config_path=str(config_path),
        environ={"ORKET_HOST": "127.0.0.9", "ORKET_PORT": "8099"},
    )
    assert settings.host == "127.0.0.5"
    assert settings.port == 8095


def test_resolve_api_launch_settings_dev_profile_enables_reload_by_default() -> None:
    settings = resolve_api_launch_settings(
        cli_host=None,
        cli_port=None,
        cli_profile="dev",
        cli_reload=None,
        config_path=None,
        environ={},
    )
    assert settings.profile == "dev"
    assert settings.reload is True


def test_resolve_api_launch_settings_rejects_reload_when_profile_not_dev() -> None:
    with pytest.raises(LauncherConfigError, match="profile=dev"):
        resolve_api_launch_settings(
            cli_host=None,
            cli_port=None,
            cli_profile=None,
            cli_reload=True,
            config_path=None,
            environ={},
        )


def test_resolve_api_launch_settings_rejects_reload_enabled_in_safe_config(tmp_path: Path) -> None:
    config_path = tmp_path / "launcher.json"
    _write_config(config_path, {"reload": True})
    with pytest.raises(LauncherConfigError, match="profile=dev"):
        resolve_api_launch_settings(
            cli_host=None,
            cli_port=None,
            cli_profile=None,
            cli_reload=None,
            config_path=str(config_path),
            environ={},
        )
