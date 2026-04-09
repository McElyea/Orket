from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from orket_extension_sdk.capabilities import CapabilityRegistry, load_capability_vocab

AUTHORIZATION_SURFACE = "host_authorized_capability_registry_v1"
AUTHORIZATION_POLICY_VERSION = "extension_capability_authorization.v1"
HOST_CONTROLS_INPUT_KEY = "__orket_host_capability_authorization__"
FIRST_SLICE_CAPABILITIES = ("model.generate", "memory.query", "memory.write")
STRUCTURAL_CONTEXT_CAPABILITIES = ("artifact.root", "workspace.root")
_CAPABILITY_FAMILIES = {
    "model.generate": "model_io",
    "memory.query": "memory_read",
    "memory.write": "memory_write",
    "speech.transcribe": "voice_input",
    "tts.speak": "voice_output",
    "audio.play": "voice_output",
    "speech.play_clip": "voice_output",
    "voice.turn_control": "turn_control",
}


@dataclass(frozen=True)
class SdkCapabilityAuditCase:
    test_case: str = ""
    expected_result: str = ""
    proof_ref: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "test_case": self.test_case,
            "expected_result": self.expected_result,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class HostCapabilityControls:
    admit_only: tuple[str, ...] = ()
    audit_case: SdkCapabilityAuditCase = SdkCapabilityAuditCase()
    child_extra_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class SdkAuthorizationEnvelope:
    extension_id: str
    workload_id: str
    run_id: str
    declared_capabilities: tuple[str, ...]
    admitted_capabilities: tuple[str, ...]
    authorization_basis: str
    policy_version: str
    authorization_digest: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "extension_id": self.extension_id,
            "workload_id": self.workload_id,
            "run_id": self.run_id,
            "declared_capabilities": list(self.declared_capabilities),
            "admitted_capabilities": list(self.admitted_capabilities),
            "authorization_basis": self.authorization_basis,
            "policy_version": self.policy_version,
            "authorization_digest": self.authorization_digest,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SdkAuthorizationEnvelope:
        return cls(
            extension_id=str(payload["extension_id"]),
            workload_id=str(payload["workload_id"]),
            run_id=str(payload["run_id"]),
            declared_capabilities=tuple(_normalize_capability_list(payload.get("declared_capabilities", ()))),
            admitted_capabilities=tuple(_normalize_capability_list(payload.get("admitted_capabilities", ()))),
            authorization_basis=str(payload["authorization_basis"]),
            policy_version=str(payload["policy_version"]),
            authorization_digest=str(payload["authorization_digest"]),
        )


def split_host_capability_controls(input_config: dict[str, Any]) -> tuple[dict[str, Any], HostCapabilityControls]:
    sanitized = dict(input_config)
    raw_controls = sanitized.pop(HOST_CONTROLS_INPUT_KEY, None)
    if not isinstance(raw_controls, dict):
        return sanitized, HostCapabilityControls()
    audit_payload = raw_controls.get("audit_case", {})
    audit_case = SdkCapabilityAuditCase(
        test_case=str((audit_payload or {}).get("test_case", "")).strip(),
        expected_result=str((audit_payload or {}).get("expected_result", "")).strip(),
        proof_ref=str((audit_payload or {}).get("proof_ref", "")).strip(),
    )
    return sanitized, HostCapabilityControls(
        admit_only=tuple(_normalize_capability_list(raw_controls.get("admit_only", ()))),
        audit_case=audit_case,
        child_extra_capabilities=tuple(_normalize_capability_list(raw_controls.get("child_extra_capabilities", ()))),
    )


def build_host_authorization_envelope(
    *,
    extension_id: str,
    workload_id: str,
    run_id: str,
    declared_capabilities: list[str],
    controls: HostCapabilityControls,
) -> SdkAuthorizationEnvelope:
    declared = _normalize_capability_list(declared_capabilities)
    invalid = sorted(set(declared) - set(load_capability_vocab()))
    if invalid:
        raise ValueError("E_SDK_CAPABILITY_DECLARED_INVALID: " + ", ".join(invalid))
    narrowed = set(controls.admit_only)
    admitted = [
        capability_id
        for capability_id in declared
        if capability_id not in FIRST_SLICE_CAPABILITIES or not narrowed or capability_id in narrowed
    ]
    digest = _authorization_digest(
        extension_id=extension_id,
        workload_id=workload_id,
        run_id=run_id,
        declared_capabilities=declared,
        admitted_capabilities=admitted,
    )
    return SdkAuthorizationEnvelope(
        extension_id=extension_id,
        workload_id=workload_id,
        run_id=run_id,
        declared_capabilities=tuple(declared),
        admitted_capabilities=tuple(admitted),
        authorization_basis=AUTHORIZATION_SURFACE,
        policy_version=AUTHORIZATION_POLICY_VERSION,
        authorization_digest=digest,
    )


def raw_registry_instantiated_capabilities(registry: CapabilityRegistry) -> list[str]:
    return sorted(str(capability_id) for capability_id in registry._providers)


def raw_registry_first_slice_capabilities(registry: CapabilityRegistry) -> set[str]:
    return {capability_id for capability_id in FIRST_SLICE_CAPABILITIES if registry.has(capability_id)}


def revalidate_child_capabilities(
    *,
    envelope: SdkAuthorizationEnvelope,
    raw_registry: CapabilityRegistry,
) -> list[str]:
    raw_first_slice = raw_registry_first_slice_capabilities(raw_registry)
    admitted_first_slice = {capability_id for capability_id in envelope.admitted_capabilities if capability_id in FIRST_SLICE_CAPABILITIES}
    drift = sorted(raw_first_slice - admitted_first_slice)
    if drift:
        raise ValueError("E_SDK_CAPABILITY_AUTHORIZATION_DRIFT: " + ", ".join(drift))
    return raw_registry_instantiated_capabilities(raw_registry)


def capability_family(capability_id: str) -> str:
    if capability_id in STRUCTURAL_CONTEXT_CAPABILITIES:
        return "structural_context"
    return _CAPABILITY_FAMILIES.get(capability_id, "other")


def capability_declared(envelope: SdkAuthorizationEnvelope, capability_id: str) -> bool:
    return capability_id in envelope.declared_capabilities


def capability_admitted(envelope: SdkAuthorizationEnvelope, capability_id: str) -> bool:
    return capability_id in envelope.admitted_capabilities


def _authorization_digest(
    *,
    extension_id: str,
    workload_id: str,
    run_id: str,
    declared_capabilities: list[str],
    admitted_capabilities: list[str],
) -> str:
    payload = {
        "admitted_capabilities": admitted_capabilities,
        "authorization_basis": AUTHORIZATION_SURFACE,
        "declared_capabilities": declared_capabilities,
        "extension_id": extension_id,
        "policy_version": AUTHORIZATION_POLICY_VERSION,
        "run_id": run_id,
        "workload_id": workload_id,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalize_capability_list(values: Any) -> list[str]:
    normalized = []
    seen: set[str] = set()
    for raw_value in list(values or ()):
        capability_id = str(raw_value or "").strip()
        if not capability_id or capability_id in seen:
            continue
        seen.add(capability_id)
        normalized.append(capability_id)
    return sorted(normalized)
