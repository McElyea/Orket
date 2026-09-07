from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

READ_ONLY_ACTIONS = frozenset({"read", "list", "inspect"})
WRITE_ACTIONS = frozenset({"write", "edit", "delete"})
COMMAND_ACTIONS = frozenset({"shell", "command", "run_shell"})
NETWORK_ACTIONS = frozenset({"network", "http", "fetch"})


@dataclass(frozen=True)
class RiskClassification:
    risk: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"risk": self.risk, "reason": self.reason}


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "approval_required": self.approval_required,
        }


@dataclass(frozen=True)
class GovernedRunPolicy:
    version: str = "governed_run_policy.v1"
    shell_allowlist: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> GovernedRunPolicy:
        raw = dict(payload or {})
        allowlist = raw.get("shell_allowlist", raw.get("allowed_shell_commands", ()))
        if allowlist is None:
            allowlist = ()
        if isinstance(allowlist, str) or not isinstance(allowlist, Sequence):
            raise ValueError("policy.shell_allowlist must be a list of exact command strings")
        return cls(
            version=str(raw.get("version") or "governed_run_policy.v1"),
            shell_allowlist=tuple(str(item).strip() for item in allowlist if str(item).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "shell_allowlist": list(self.shell_allowlist)}


def action_kind(action: Mapping[str, Any]) -> str:
    return str(action.get("kind") or action.get("type") or "").strip().lower()


def classify_action(action: Mapping[str, Any]) -> RiskClassification:
    kind = action_kind(action)
    if kind in READ_ONLY_ACTIONS:
        return RiskClassification("read_only", "read/list/inspect actions are read-only observations")
    if kind in WRITE_ACTIONS:
        return RiskClassification("write", "write/edit/delete actions can mutate workspace state")
    if kind in COMMAND_ACTIONS:
        return RiskClassification("command", "shell commands can mutate state or escape policy boundaries")
    if kind in NETWORK_ACTIONS:
        return RiskClassification("network", "network actions can exfiltrate data or depend on external services")
    return RiskClassification("unknown", "unknown actions deny by default")


def decide_action(action: Mapping[str, Any], policy: GovernedRunPolicy) -> PolicyDecision:
    classification = classify_action(action)
    if classification.risk == "read_only":
        return PolicyDecision("allow", "read-only observation allowed")
    if classification.risk == "write":
        return PolicyDecision("requires_approval", "write operation requires human approval", True)
    if classification.risk == "command":
        command = str(action.get("command") or action.get("target") or "")
        if command.strip() and command in policy.shell_allowlist:
            return PolicyDecision("allow", "shell command is explicitly allowlisted")
        return PolicyDecision("deny", "shell command is not in the allowlist")
    if classification.risk == "network":
        return PolicyDecision("deny", "network actions are denied by default")
    return PolicyDecision("deny", "unknown action kind is denied by default")
