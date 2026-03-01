from __future__ import annotations

import os
from typing import Any

from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.runtime_policy import (
    resolve_gitea_state_pilot_enabled,
    resolve_state_backend_mode,
)
from orket.settings import load_user_settings


class OrchestrationConfig:
    """Configuration resolution and validation for orchestration runtime mode."""

    def __init__(self, org: Any) -> None:
        self.org = org

    def resolve_state_backend_mode(self) -> str:
        env_raw = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("state_backend_mode", "")).strip()
        user_raw = str(load_user_settings().get("state_backend_mode", "")).strip()
        return resolve_state_backend_mode(env_raw, process_raw, user_raw)

    def resolve_gitea_state_pilot_enabled(self) -> bool:
        env_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("gitea_state_pilot_enabled", "")).strip()
        user_raw = str(load_user_settings().get("gitea_state_pilot_enabled", "")).strip()
        return bool(resolve_gitea_state_pilot_enabled(env_raw, process_raw, user_raw))

    def validate_state_backend_mode(self, state_backend_mode: str, gitea_state_pilot_enabled: bool) -> None:
        if state_backend_mode != "gitea":
            return
        env_mode = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip().lower()
        env_pilot_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        if env_mode == "gitea" and not env_pilot_raw:
            raise NotImplementedError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        if not gitea_state_pilot_enabled:
            raise NotImplementedError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise NotImplementedError(f"State backend mode 'gitea' pilot readiness failed: {failures}")
