from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from orket.core.domain import CapabilityClass

from .control_plane_models import WorkloadRecord
from .workload_contract import WORKLOAD_CONTRACT_VERSION_V1, WorkloadContractV1, parse_workload_contract


def _build_control_plane_workload_record(
    *,
    workload_id: str,
    workload_version: str,
    input_contract_ref: str,
    output_contract_ref: str,
    declared_capabilities: Sequence[CapabilityClass] = (),
    declared_namespace_scopes: Sequence[str] = (),
    declared_resource_classes: Sequence[str] = (),
    declared_degraded_modes: Sequence[str] = (),
    recovery_policy_refs: Sequence[str] = (),
    reconciliation_requirements: Sequence[str] = (),
    definition_payload: Mapping[str, Any] | None = None,
) -> WorkloadRecord:
    normalized_capabilities = _normalize_capabilities(declared_capabilities)
    normalized_namespace_scopes = _normalize_strings(declared_namespace_scopes)
    normalized_resource_classes = _normalize_strings(declared_resource_classes)
    normalized_degraded_modes = _normalize_strings(declared_degraded_modes)
    normalized_recovery_policy_refs = _normalize_strings(recovery_policy_refs)
    normalized_reconciliation_requirements = _normalize_strings(reconciliation_requirements)
    normalized_definition_payload = dict(definition_payload or {})
    digest_payload = {
        "workload_id": str(workload_id).strip(),
        "workload_version": str(workload_version).strip(),
        "declared_capabilities": [capability.value for capability in normalized_capabilities],
        "declared_namespace_scopes": normalized_namespace_scopes,
        "declared_resource_classes": normalized_resource_classes,
        "declared_degraded_modes": normalized_degraded_modes,
        "input_contract_ref": str(input_contract_ref).strip(),
        "output_contract_ref": str(output_contract_ref).strip(),
        "recovery_policy_refs": normalized_recovery_policy_refs,
        "reconciliation_requirements": normalized_reconciliation_requirements,
        "definition_payload": normalized_definition_payload,
    }
    workload_digest = "sha256:" + hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return WorkloadRecord(
        workload_id=str(workload_id).strip(),
        workload_version=str(workload_version).strip(),
        workload_digest=workload_digest,
        declared_capabilities=list(normalized_capabilities),
        declared_namespace_scopes=normalized_namespace_scopes,
        declared_resource_classes=normalized_resource_classes,
        declared_degraded_modes=normalized_degraded_modes,
        input_contract_ref=str(input_contract_ref).strip(),
        output_contract_ref=str(output_contract_ref).strip(),
        recovery_policy_refs=normalized_recovery_policy_refs,
        reconciliation_requirements=normalized_reconciliation_requirements,
    )


def _build_control_plane_workload_record_from_workload_contract(
    *,
    workload_id: str,
    contract_payload: WorkloadContractV1 | Mapping[str, Any],
    output_contract_ref: str,
    declared_capabilities: Sequence[CapabilityClass] = (),
    declared_namespace_scopes: Sequence[str] = (),
    declared_resource_classes: Sequence[str] = (),
    declared_degraded_modes: Sequence[str] = (),
    recovery_policy_refs: Sequence[str] = (),
    reconciliation_requirements: Sequence[str] = (),
    definition_payload: Mapping[str, Any] | None = None,
) -> WorkloadRecord:
    contract = (
        contract_payload
        if isinstance(contract_payload, WorkloadContractV1)
        else parse_workload_contract(dict(contract_payload))
    )
    combined_definition_payload = {
        "workload_contract": contract.model_dump(mode="json"),
        **dict(definition_payload or {}),
    }
    return _build_control_plane_workload_record(
        workload_id=workload_id,
        workload_version=WORKLOAD_CONTRACT_VERSION_V1,
        input_contract_ref="docs/specs/WORKLOAD_CONTRACT_V1.md",
        output_contract_ref=output_contract_ref,
        declared_capabilities=declared_capabilities,
        declared_namespace_scopes=declared_namespace_scopes,
        declared_resource_classes=declared_resource_classes,
        declared_degraded_modes=declared_degraded_modes,
        recovery_policy_refs=recovery_policy_refs,
        reconciliation_requirements=reconciliation_requirements,
        definition_payload=combined_definition_payload,
    )


def _normalize_capabilities(capabilities: Sequence[CapabilityClass]) -> list[CapabilityClass]:
    unique = {
        capability if isinstance(capability, CapabilityClass) else CapabilityClass(str(capability).strip())
        for capability in capabilities
    }
    return sorted(unique, key=lambda capability: capability.value)


def _normalize_strings(values: Sequence[str]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


__all__: list[str] = []
