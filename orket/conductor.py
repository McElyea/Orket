from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from orket.logging import log_model_selected, log_event


@dataclass
class ConductorAdjustment:
    skip_role: bool = False
    prompt_patch: Optional[str] = None


@dataclass
class SessionView:
    flow_name: str
    step_index: int
    role: str
    transcript: List[Dict[str, Any]]
    notes: Dict[str, Any]


class Conductor:
    """Base class for all conductors."""

    def before_step(self, step: Dict[str, Any], session: SessionView) -> ConductorAdjustment:
        return ConductorAdjustment()

    def after_step(self, step: Dict[str, Any], session: SessionView) -> None:
        return

    # Optional hooks for model logging; can be called from orchestrator
    def log_session_models(self, band, provider, workspace, flow_name: str) -> None:
        for role_name in band.roles.keys():
            log_model_selected(
                role=role_name,
                model=getattr(provider, "model", "unknown"),
                temperature=getattr(provider, "temperature", None),
                seed=getattr(provider, "seed", None),
                flow=flow_name,
                workspace=workspace,
            )

    def log_model_override(self, role: str, new_model: str, flow_name: str, workspace) -> None:
        log_event(
            "model_override",
            {
                "role": role,
                "new_model": new_model,
                "flow": flow_name,
            },
            workspace=workspace,
        )

    def log_fallback(self, role: str, from_model: str, to_model: str, flow_name: str, workspace) -> None:
        log_event(
            "model_fallback",
            {
                "role": role,
                "from_model": from_model,
                "to_model": to_model,
                "flow": flow_name,
            },
            workspace=workspace,
        )


class ManualConductor(Conductor):
    """
    A manual, interactive conductor that:
      - enables/disables roles
      - applies prompt patches
      - can skip roles
    """

    def __init__(self):
        self.enabled_roles: Dict[str, bool] = {}
        self.prompt_overrides: Dict[str, str] = {}

    def ensure_role_known(self, role: str) -> None:
        if role not in self.enabled_roles:
            self.enabled_roles[role] = True

    def disable(self, role: str) -> None:
        self.ensure_role_known(role)
        self.enabled_roles[role] = False

    def enable(self, role: str) -> None:
        self.ensure_role_known(role)
        self.enabled_roles[role] = True

    def patch_prompt(self, role: str, text: str) -> None:
        self.prompt_overrides[role] = text

    def clear_prompt_patch(self, role: str) -> None:
        self.prompt_overrides.pop(role, None)

    def before_step(self, step: Dict[str, Any], session: SessionView) -> ConductorAdjustment:
        role = step["role"]
        self.ensure_role_known(role)

        if not self.enabled_roles.get(role, True):
            return ConductorAdjustment(skip_role=True)

        patch = self.prompt_overrides.get(role)
        return ConductorAdjustment(prompt_patch=patch)

    def after_step(self, step: Dict[str, Any], session: SessionView) -> None:
        return
