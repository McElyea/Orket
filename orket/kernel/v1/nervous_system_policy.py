from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from orket.application.services.kernel_invocation_inputs import capture_kernel_environment


@dataclass(frozen=True)
class NervousSystemPolicyInputs:
    enabled: bool
    allow_pre_resolved_flags: bool
    use_profile_resolver: bool

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in (
            self.enabled, self.allow_pre_resolved_flags, self.use_profile_resolver,
        )):
            raise TypeError("E_KERNEL_POLICY_BOOLEAN_REQUIRED")


def _flag(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def capture_nervous_system_policy_inputs(
    *, environment: Mapping[str, str] | None = None,
) -> NervousSystemPolicyInputs:
    observed = capture_kernel_environment(environment).values
    return NervousSystemPolicyInputs(
        enabled=_flag(observed.get("ORKET_ENABLE_NERVOUS_SYSTEM")),
        allow_pre_resolved_flags=_flag(observed.get("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS")),
        use_profile_resolver=_flag(observed.get("ORKET_USE_TOOL_PROFILE_RESOLVER"), default=True),
    )


def require_nervous_system_enabled(policy_inputs: NervousSystemPolicyInputs | None = None) -> None:
    selected = capture_nervous_system_policy_inputs() if policy_inputs is None else policy_inputs
    if not isinstance(selected, NervousSystemPolicyInputs):
        raise TypeError("E_KERNEL_POLICY_INPUT_REQUIRED")
    if selected.enabled:
        return
    raise ValueError("Nervous System v1 is disabled (set ORKET_ENABLE_NERVOUS_SYSTEM=true).")


def allow_pre_resolved_policy_flags() -> bool:
    return capture_nervous_system_policy_inputs().allow_pre_resolved_flags


def use_tool_profile_resolver() -> bool:
    return capture_nervous_system_policy_inputs().use_profile_resolver


def is_exfil_payload(payload: dict[str, Any]) -> bool:
    tool_profile = payload.get("tool_profile")
    if isinstance(tool_profile, dict) and bool(tool_profile.get("exfil")):
        return True
    target = payload.get("target")
    return bool(isinstance(target, str) and _is_non_local_target(target))


def _is_non_local_target(target: str) -> bool:
    text = str(target or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https", "ws", "wss", "ftp"}:
        return True
    if parsed.netloc:
        return True
    lower = text.lower()
    if lower.startswith("ssh://") or lower.startswith("tcp://") or lower.startswith("udp://"):
        return True
    if "://" in text:
        return True
    if "@" in text and ":" in text and "/" in text:
        return True
    if "\\" in text:
        return False
    if "/" in text or text.startswith("."):
        return False
    if "." in text and all(ch not in text for ch in ("/", "\\")):
        return True
    try:
        _ = Path(text)
    except (TypeError, ValueError, OSError):
        return True
    return False


__all__ = [
    "NervousSystemPolicyInputs",
    "capture_nervous_system_policy_inputs",
    "allow_pre_resolved_policy_flags",
    "is_exfil_payload",
    "require_nervous_system_enabled",
    "use_tool_profile_resolver",
]
