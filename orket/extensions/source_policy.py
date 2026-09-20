"""Pure source admission over an explicitly captured installation environment."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourcePolicyDecision:
    security_mode: str
    security_profile: str
    security_policy_version: str
    trust_profile: str
    compat_fallbacks: tuple[str, ...]


def evaluate_source_policy(repo: str, environment: Mapping[str, str]) -> SourcePolicyDecision:
    mode = str(environment.get("ORKET_EXT_SECURITY_MODE", "compat")).strip().lower() or "compat"
    profile = str(environment.get("ORKET_EXT_SECURITY_PROFILE", "production")).strip().lower() or "production"
    allowed_hosts_raw = str(
        environment.get("ORKET_EXT_ALLOWED_HOSTS", "github.com,gitlab.com,gitea.local,localhost")
    ).strip()
    allowed_hosts = {item.strip().lower() for item in allowed_hosts_raw.split(",") if item.strip()}
    allowed_protocols = {"https", "ssh"}
    fallback_codes: list[str] = []

    source_kind, protocol, host = classify_repo_source(repo)
    production = profile == "production"
    enforce = mode == "enforce"

    def _deny_or_fallback(code: str, fallback_code: str) -> None:
        if production and enforce:
            raise RuntimeError(code)
        fallback_codes.append(fallback_code)

    if source_kind == "local":
        if production:
            _deny_or_fallback("E_EXT_TRUST_SOURCE_LOCAL_PATH_DENIED", "EXT_LOCAL_PATH_COMPAT")
        else:
            fallback_codes.append("DEV_PROFILE_EXCEPTION_LOCAL_PATH")
    else:
        if protocol and protocol not in allowed_protocols and production:
            _deny_or_fallback("E_EXT_TRUST_PROTOCOL_DENIED", "EXT_PROTOCOL_COMPAT")
        if host and host not in allowed_hosts and production:
            _deny_or_fallback("E_EXT_TRUST_HOST_DENIED", "EXT_HOST_COMPAT")

    return SourcePolicyDecision(
        security_mode=mode,
        security_profile=profile,
        security_policy_version=hashlib.sha256(
            str(
                {
                    "mode": mode,
                    "profile": profile,
                    "allowed_hosts": sorted(allowed_hosts),
                    "allowed_protocols": sorted(allowed_protocols),
                }
            ).encode("utf-8")
        ).hexdigest(),
        trust_profile=profile,
        compat_fallbacks=tuple(sorted(set(fallback_codes))),
    )


def classify_repo_source(repo: str) -> tuple[str, str, str]:
    value = str(repo or "").strip()
    if not value:
        return ("local", "", "")
    path_candidate = Path(value)
    if path_candidate.is_absolute() or value.startswith("."):
        return ("local", "file", "localhost")
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and (parsed.username is not None or parsed.password is not None):
        raise ValueError("E_EXT_SOURCE_INLINE_CREDENTIALS_DENIED")
    if parsed.scheme:
        protocol = parsed.scheme.strip().lower()
        host = (parsed.hostname or "").strip().lower()
        if protocol == "file":
            return ("local", protocol, host or "localhost")
        return ("remote", protocol, host)
    if re.match(r"^[^@]+@[^:]+:.+$", value):
        host = value.split("@", 1)[1].split(":", 1)[0].strip().lower()
        return ("remote", "ssh", host)
    return ("local", "file", "localhost")
