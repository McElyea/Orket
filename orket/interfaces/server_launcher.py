from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8082
DEFAULT_PROFILE = "safe"
ALLOWED_PROFILES = ("safe", "dev")


class LauncherConfigError(ValueError):
    """Raised when launcher inputs are invalid or unsafe."""


@dataclass(frozen=True)
class ApiLaunchSettings:
    host: str
    port: int
    reload: bool
    profile: str
    config_path: str


def build_api_server_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Orket API server.")
    parser.add_argument("--host", default="", help=f"Bind host. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=0, help=f"Bind port. Default: {DEFAULT_PORT}")
    parser.add_argument("--config", default="", help="Optional JSON launcher config path.")
    parser.add_argument("--profile", choices=ALLOWED_PROFILES, default="", help="Startup profile: safe or dev.")
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument("--reload", dest="reload", action="store_true", help="Enable reload (dev profile only).")
    reload_group.add_argument("--no-reload", dest="reload", action="store_false", help="Disable reload explicitly.")
    parser.set_defaults(reload=None)
    return parser


def _normalize_port(raw: Any, *, field: str) -> int:
    try:
        port = int(raw)
    except (TypeError, ValueError) as exc:
        raise LauncherConfigError(f"{field} must be an integer") from exc
    if port < 1 or port > 65535:
        raise LauncherConfigError(f"{field} must be between 1 and 65535")
    return port


def _parse_bool(raw: Any, *, field: str) -> bool:
    if isinstance(raw, bool):
        return raw
    token = str(raw).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    raise LauncherConfigError(f"{field} must be a boolean-like value")


def _normalize_profile(raw: Any, *, field: str) -> str:
    profile = str(raw or "").strip().lower()
    if not profile:
        return DEFAULT_PROFILE
    if profile not in ALLOWED_PROFILES:
        raise LauncherConfigError(f"{field} must be one of: {', '.join(ALLOWED_PROFILES)}")
    return profile


def _load_launcher_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}
    if not config_path.exists():
        raise LauncherConfigError(f"config file not found: {config_path}")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LauncherConfigError(f"config file is not valid JSON: {config_path}") from exc
    if not isinstance(payload, dict):
        raise LauncherConfigError("config root must be a JSON object")
    return payload


def _optional_text(raw: Any) -> str | None:
    token = str(raw or "").strip()
    return token if token else None


def resolve_api_launch_settings(
    *,
    cli_host: str | None,
    cli_port: int | None,
    cli_profile: str | None,
    cli_reload: bool | None,
    config_path: str | Path | None,
    environ: Mapping[str, str] | None = None,
) -> ApiLaunchSettings:
    env = environ if environ is not None else os.environ
    config_path_obj = Path(str(config_path)).resolve() if _optional_text(config_path) else None
    config = _load_launcher_config(config_path_obj)

    profile = DEFAULT_PROFILE
    config_profile = config.get("profile")
    if config_profile is not None:
        profile = _normalize_profile(config_profile, field="config.profile")
    if _optional_text(cli_profile):
        profile = _normalize_profile(cli_profile, field="--profile")

    host = DEFAULT_HOST
    env_host = _optional_text(env.get("ORKET_HOST"))
    if env_host:
        host = env_host
    config_host = _optional_text(config.get("host"))
    if config_host:
        host = config_host
    if _optional_text(cli_host):
        host = str(cli_host).strip()

    port = DEFAULT_PORT
    env_port = _optional_text(env.get("ORKET_PORT"))
    if env_port:
        port = _normalize_port(env_port, field="ORKET_PORT")
    if config.get("port") is not None and str(config.get("port")).strip():
        port = _normalize_port(config.get("port"), field="config.port")
    if cli_port is not None:
        port = _normalize_port(cli_port, field="--port")

    reload_enabled = profile == "dev"
    if config.get("reload") is not None:
        reload_enabled = _parse_bool(config.get("reload"), field="config.reload")
    if cli_reload is not None:
        reload_enabled = bool(cli_reload)
    if reload_enabled and profile != "dev":
        raise LauncherConfigError("reload may only be enabled with profile=dev")

    resolved_config_path = str(config_path_obj).replace("\\", "/") if config_path_obj else ""
    return ApiLaunchSettings(
        host=str(host).strip(),
        port=int(port),
        reload=bool(reload_enabled),
        profile=profile,
        config_path=resolved_config_path,
    )


def resolve_api_launch_settings_from_namespace(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str] | None = None,
) -> ApiLaunchSettings:
    return resolve_api_launch_settings(
        cli_host=_optional_text(getattr(args, "host", "")),
        cli_port=int(getattr(args, "port", 0)) if int(getattr(args, "port", 0)) > 0 else None,
        cli_profile=_optional_text(getattr(args, "profile", "")),
        cli_reload=getattr(args, "reload", None),
        config_path=_optional_text(getattr(args, "config", "")),
        environ=environ,
    )
