from __future__ import annotations

from typing import Any


STATE_TRANSITION_REGISTRY_SCHEMA_VERSION = "1.0"


_REGISTRY: dict[str, dict[str, Any]] = {
    "session": {
        "states": ("running", "done", "failed", "terminal_failure", "incomplete", "blocked", "degraded"),
        "transitions": {
            "running": ("done", "failed", "terminal_failure", "incomplete", "blocked", "degraded"),
            "incomplete": ("running", "failed", "terminal_failure"),
            "failed": ("running",),
            "terminal_failure": ("running",),
            "blocked": ("running",),
            "degraded": ("running", "done", "failed", "terminal_failure"),
            "done": ("running",),
        },
    },
    "run": {
        "states": ("running", "done", "failed", "terminal_failure", "incomplete", "blocked", "degraded"),
        "transitions": {
            "running": ("done", "failed", "terminal_failure", "incomplete", "blocked", "degraded"),
            "incomplete": ("running", "failed", "terminal_failure"),
            "failed": ("running",),
            "terminal_failure": ("running",),
            "blocked": ("running",),
            "degraded": ("running", "done", "failed", "terminal_failure"),
            "done": ("running",),
        },
    },
    "tool_invocation": {
        "states": ("pending", "executing", "succeeded", "failed", "canceled", "rejected"),
        "transitions": {
            "pending": ("executing", "canceled", "rejected"),
            "executing": ("succeeded", "failed", "canceled"),
            "failed": ("pending",),
            "rejected": ("pending",),
            "canceled": ("pending",),
            "succeeded": (),
        },
    },
    "voice": {
        "states": ("idle", "capturing", "transcribing", "synthesizing", "playing", "degraded", "blocked"),
        "transitions": {
            "idle": ("capturing", "synthesizing", "degraded", "blocked"),
            "capturing": ("transcribing", "idle", "degraded", "blocked"),
            "transcribing": ("idle", "degraded", "blocked"),
            "synthesizing": ("playing", "idle", "degraded", "blocked"),
            "playing": ("idle", "degraded", "blocked"),
            "degraded": ("idle", "capturing", "synthesizing", "blocked"),
            "blocked": ("idle",),
        },
    },
    "ui": {
        "states": ("ready", "busy", "degraded", "blocked", "error"),
        "transitions": {
            "ready": ("busy", "degraded", "blocked", "error"),
            "busy": ("ready", "degraded", "blocked", "error"),
            "degraded": ("ready", "busy", "blocked", "error"),
            "blocked": ("ready", "degraded"),
            "error": ("ready", "degraded", "blocked"),
        },
    },
}


def state_transition_registry_snapshot() -> dict[str, object]:
    domains: list[dict[str, object]] = []
    for domain_name, payload in _REGISTRY.items():
        states = tuple(str(state) for state in payload["states"])
        transitions = dict(payload["transitions"])
        domains.append(
            {
                "domain": domain_name,
                "states": list(states),
                "transitions": [
                    {
                        "from": source,
                        "to": list(tuple(str(token) for token in targets)),
                    }
                    for source, targets in transitions.items()
                ],
            }
        )
    return {
        "schema_version": STATE_TRANSITION_REGISTRY_SCHEMA_VERSION,
        "domains": domains,
    }


def _resolve_domain(domain: str) -> dict[str, Any]:
    token = str(domain or "").strip().lower()
    payload = _REGISTRY.get(token)
    if payload is None:
        raise ValueError(f"E_STATE_DOMAIN_UNKNOWN:{token or '<empty>'}")
    return payload


def validate_state_token(*, domain: str, state: str) -> str:
    payload = _resolve_domain(domain)
    normalized_state = str(state or "").strip().lower()
    if normalized_state not in tuple(str(token) for token in payload["states"]):
        raise ValueError(f"E_STATE_TOKEN_UNKNOWN:{str(domain or '').strip().lower()}:{normalized_state or '<empty>'}")
    return normalized_state


def validate_state_transition(*, domain: str, from_state: str, to_state: str) -> tuple[str, str]:
    payload = _resolve_domain(domain)
    resolved_from = validate_state_token(domain=domain, state=from_state)
    resolved_to = validate_state_token(domain=domain, state=to_state)
    transitions = payload["transitions"]
    allowed_targets = tuple(str(token) for token in transitions.get(resolved_from, ()))
    if resolved_to not in allowed_targets:
        raise ValueError(f"E_STATE_TRANSITION_INVALID:{str(domain or '').strip().lower()}:{resolved_from}->{resolved_to}")
    return resolved_from, resolved_to
