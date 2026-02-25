from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from orket.core.domain.module_manifest import ModuleManifest
from orket.settings import load_user_settings


DEFAULT_MODULE_PROFILE = "developer-local"
RUNTIME_MODULE_CONTRACT_VERSION = "1.0.0"

PROFILE_MODULES: Dict[str, List[str]] = {
    "engine-only": ["engine"],
    "developer-local": ["engine", "cli", "api", "webhook"],
    "api-runtime": ["engine", "api"],
    "api-webhook-runtime": ["engine", "api", "webhook"],
}


def built_in_manifests() -> Dict[str, ModuleManifest]:
    return {
        "engine": ModuleManifest(
            module_id="engine",
            module_version="1.0.0",
            capabilities=["engine.runtime", "engine.orchestration"],
            required_modules=[],
            entrypoints=["orket.orchestration.engine:OrchestrationEngine"],
            contract_version_range=">=1.0.0,<2.0.0",
        ),
        "cli": ModuleManifest(
            module_id="cli",
            module_version="1.0.0",
            capabilities=["cli.runtime"],
            required_modules=["engine"],
            entrypoints=["orket.interfaces.cli:run_cli"],
            contract_version_range=">=1.0.0,<2.0.0",
        ),
        "api": ModuleManifest(
            module_id="api",
            module_version="1.0.0",
            capabilities=["api.http.v1"],
            required_modules=["engine"],
            entrypoints=["orket.interfaces.api:create_api_app"],
            contract_version_range=">=1.0.0,<2.0.0",
        ),
        "webhook": ModuleManifest(
            module_id="webhook",
            module_version="1.0.0",
            capabilities=["webhook.gitea.v1"],
            required_modules=["engine"],
            entrypoints=["orket.webhook_server:create_webhook_app"],
            contract_version_range=">=1.0.0,<2.0.0",
        ),
    }


@dataclass(frozen=True)
class ModuleResolutionError(Exception):
    code: str
    message: str
    detail: dict

    def to_payload(self) -> dict:
        return {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
        }


def resolve_module_profile(explicit_profile: str | None = None) -> str:
    if explicit_profile and explicit_profile.strip():
        return explicit_profile.strip().lower()

    env_profile = (os.environ.get("ORKET_MODULE_PROFILE") or "").strip().lower()
    if env_profile:
        return env_profile

    settings_profile = str(load_user_settings().get("module_profile", "") or "").strip().lower()
    if settings_profile:
        return settings_profile

    return DEFAULT_MODULE_PROFILE


def modules_for_profile(profile: str) -> List[str]:
    normalized = (profile or "").strip().lower()
    if normalized not in PROFILE_MODULES:
        raise ModuleResolutionError(
            code="E_MODULE_PROFILE_UNKNOWN",
            message=f"Unknown module profile '{profile}'.",
            detail={"profile": profile, "known_profiles": sorted(PROFILE_MODULES.keys())},
        )
    return list(PROFILE_MODULES[normalized])


def _enabled_module_set(profile: str) -> Set[str]:
    return set(modules_for_profile(profile))


def ensure_module_enabled(module_id: str, profile: str, manifests: Dict[str, ModuleManifest] | None = None) -> None:
    manifests = manifests or built_in_manifests()
    if module_id not in manifests:
        raise ModuleResolutionError(
            code="E_MODULE_NOT_FOUND",
            message=f"Module '{module_id}' is not registered.",
            detail={"module_id": module_id, "known_modules": sorted(manifests.keys())},
        )

    enabled = _enabled_module_set(profile)
    if module_id not in enabled:
        raise ModuleResolutionError(
            code="E_MODULE_DISABLED_BY_PROFILE",
            message=f"Module '{module_id}' is not enabled for profile '{profile}'.",
            detail={"module_id": module_id, "profile": profile, "enabled_modules": sorted(enabled)},
        )

    manifest = manifests[module_id]
    if not _is_contract_compatible(manifest.contract_version_range, RUNTIME_MODULE_CONTRACT_VERSION):
        raise ModuleResolutionError(
            code="E_MODULE_CONTRACT_INCOMPATIBLE",
            message=f"Module '{module_id}' contract range is incompatible with runtime contract version.",
            detail={
                "module_id": module_id,
                "module_contract_version_range": manifest.contract_version_range,
                "runtime_contract_version": RUNTIME_MODULE_CONTRACT_VERSION,
            },
        )

    missing_deps = [dep for dep in manifest.required_modules if dep not in enabled]
    if missing_deps:
        raise ModuleResolutionError(
            code="E_MODULE_DEPENDENCY_MISSING",
            message=f"Module '{module_id}' has missing required modules.",
            detail={"module_id": module_id, "profile": profile, "missing_required_modules": missing_deps},
        )


def ensure_capability_enabled(capability: str, profile: str, manifests: Dict[str, ModuleManifest] | None = None) -> str:
    manifests = manifests or built_in_manifests()
    enabled = _enabled_module_set(profile)

    provider: str | None = None
    for module_id, manifest in manifests.items():
        if capability in manifest.capabilities:
            provider = module_id
            break
    if provider is None:
        raise ModuleResolutionError(
            code="E_CAPABILITY_NOT_FOUND",
            message=f"Capability '{capability}' is not registered.",
            detail={"capability": capability},
        )

    if provider not in enabled:
        raise ModuleResolutionError(
            code="E_CAPABILITY_DISABLED_BY_PROFILE",
            message=f"Capability '{capability}' is not enabled for profile '{profile}'.",
            detail={
                "capability": capability,
                "provider_module": provider,
                "profile": profile,
                "enabled_modules": sorted(enabled),
            },
        )

    ensure_module_enabled(provider, profile, manifests=manifests)
    return provider


def profiles() -> Iterable[str]:
    return tuple(sorted(PROFILE_MODULES.keys()))


def _parse_version(value: str) -> tuple[int, int, int]:
    core = str(value or "").strip().split(".", 2)
    padded = (core + ["0", "0", "0"])[:3]
    try:
        return int(padded[0]), int(padded[1]), int(padded[2])
    except ValueError:
        return (0, 0, 0)


def _is_contract_compatible(contract_range: str, runtime_version: str = RUNTIME_MODULE_CONTRACT_VERSION) -> bool:
    raw = str(contract_range or "").strip()
    if not raw:
        return False
    current = _parse_version(runtime_version)
    for token in [part.strip() for part in raw.split(",") if part.strip()]:
        if token.startswith(">="):
            if current < _parse_version(token[2:]):
                return False
        elif token.startswith(">"):
            if current <= _parse_version(token[1:]):
                return False
        elif token.startswith("<="):
            if current > _parse_version(token[2:]):
                return False
        elif token.startswith("<"):
            if current >= _parse_version(token[1:]):
                return False
        elif token.startswith("=="):
            if current != _parse_version(token[2:]):
                return False
    return True
