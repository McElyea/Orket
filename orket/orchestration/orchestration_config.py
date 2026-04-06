from __future__ import annotations

import os
from typing import Any

from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.runtime_policy import (
    resolve_gitea_state_pilot_enabled,
    resolve_run_ledger_mode,
    resolve_state_backend_mode,
)
from orket.settings import load_user_settings


class OrchestrationConfig:
    """Configuration resolution and validation for orchestration runtime mode."""

    def __init__(self, org: Any) -> None:
        self.org = org

    def _process_rule(self, key: str) -> str:
        process_rules = getattr(self.org, "process_rules", None) if self.org else None
        if isinstance(process_rules, dict):
            return str(process_rules.get(key, "")).strip()
        if hasattr(process_rules, "get"):
            return str(process_rules.get(key, "")).strip()
        if process_rules is not None:
            return str(getattr(process_rules, key, "")).strip()
        return ""

    def resolve_state_backend_mode(self, *, user_settings: dict[str, Any] | None = None) -> str:
        env_raw = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip()
        process_raw = self._process_rule("state_backend_mode")
        settings = user_settings if isinstance(user_settings, dict) else load_user_settings()
        user_raw = str(settings.get("state_backend_mode", "")).strip()
        return resolve_state_backend_mode(env_raw, process_raw, user_raw)

    def resolve_run_ledger_mode(self, *, user_settings: dict[str, Any] | None = None) -> str:
        env_raw = (os.environ.get("ORKET_RUN_LEDGER_MODE") or "").strip()
        process_raw = self._process_rule("run_ledger_mode")
        settings = user_settings if isinstance(user_settings, dict) else load_user_settings()
        user_raw = str(settings.get("run_ledger_mode", "")).strip()
        return resolve_run_ledger_mode(env_raw, process_raw, user_raw)

    def resolve_gitea_state_pilot_enabled(self, *, user_settings: dict[str, Any] | None = None) -> bool:
        env_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        process_raw = self._process_rule("gitea_state_pilot_enabled")
        settings = user_settings if isinstance(user_settings, dict) else load_user_settings()
        user_raw = str(settings.get("gitea_state_pilot_enabled", "")).strip()
        return bool(resolve_gitea_state_pilot_enabled(env_raw, process_raw, user_raw))

    def validate_state_backend_mode(self, state_backend_mode: str, gitea_state_pilot_enabled: bool) -> None:
        if state_backend_mode != "gitea":
            return
        env_mode = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip().lower()
        env_pilot_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        if env_mode == "gitea" and not env_pilot_raw:
            raise ValueError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        if not gitea_state_pilot_enabled:
            raise ValueError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise ValueError(f"State backend mode 'gitea' pilot readiness failed: {failures}")
