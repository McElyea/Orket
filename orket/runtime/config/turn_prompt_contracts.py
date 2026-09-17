"""Pure prompt selection from explicit application runtime inputs."""
from __future__ import annotations

from typing import Any


def runtime_verifier_prompt_enabled(context: dict[str, Any]) -> bool:
    if not context.get("runtime_verifier_enabled", True):
        return False
    artifact = context.get("artifact_contract")
    if not isinstance(artifact, dict) or str(artifact.get("kind") or "").strip().lower() in {"", "none"}:
        return False
    traits = context.get("profile_traits")
    traits = traits if isinstance(traits, dict) else {}
    contract = context.get("runtime_verifier_contract")
    return bool(traits.get("runtime_verifier_allowed", True)) or (
        isinstance(contract, dict) and bool(contract)
        and str(traits.get("intent") or "").strip().lower() in {"write_artifact", "build_app"}
    )
