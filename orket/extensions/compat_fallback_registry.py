from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CompatFallbackRule:
    fallback_code: str
    introduced_in: str
    expiry_version: str
    removal_phase: str


_RULES: tuple[CompatFallbackRule, ...] = (
    CompatFallbackRule(
        fallback_code="EXT_LOCAL_PATH_COMPAT",
        introduced_in="0.3.16",
        expiry_version="0.5.0",
        removal_phase="phase2",
    ),
    CompatFallbackRule(
        fallback_code="EXT_PROTOCOL_COMPAT",
        introduced_in="0.3.16",
        expiry_version="0.5.0",
        removal_phase="phase2",
    ),
    CompatFallbackRule(
        fallback_code="EXT_HOST_COMPAT",
        introduced_in="0.3.16",
        expiry_version="0.5.0",
        removal_phase="phase2",
    ),
    CompatFallbackRule(
        fallback_code="DEV_PROFILE_EXCEPTION_LOCAL_PATH",
        introduced_in="0.3.16",
        expiry_version="0.6.0",
        removal_phase="phase5",
    ),
)


def iter_compat_fallback_rules() -> Iterable[CompatFallbackRule]:
    return tuple(_RULES)


def compat_fallback_codes() -> set[str]:
    return {rule.fallback_code for rule in _RULES}
