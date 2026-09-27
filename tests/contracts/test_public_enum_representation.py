"""Contract: retained public enums distinguish diagnostic text from wire values."""

from __future__ import annotations

import json
from enum import Enum
from importlib import import_module

import pytest
from pydantic import TypeAdapter

from orket.core.domain.workitem_transition import TransitionErrorCode, TransitionResult
from orket.core.types import CardStatus, CardType, WaitReason
from orket.schema import BaseCardConfig
from orket.streaming.model_provider import ProviderEvent, ProviderEventType

pytestmark = pytest.mark.contract

# Declaration names define this compatibility scope; values remain owned by product enums.
ENUM_SCOPE = [
    (
        "orket.core.domain.control_plane_enums",
        [
            "RunState",
            "AttemptState",
            "FailurePlane",
            "ExecutionFailureClass",
            "ProtocolFailureClass",
            "TruthFailureClass",
            "ResourceFailureClass",
            "ControlPlaneFailureClass",
            "SideEffectBoundaryClass",
            "RecoveryActionClass",
            "CapabilityClass",
            "EffectClass",
            "IdempotencyClass",
            "CompensationClass",
            "EvidenceContractClass",
            "ObservabilityClass",
            "ReservationKind",
            "ReservationStatus",
            "LeaseStatus",
            "CleanupAuthorityClass",
            "OwnershipClass",
            "OrphanClassification",
            "DivergenceClass",
            "SafeContinuationClass",
            "OperatorInputClass",
            "OperatorCommandClass",
            "CheckpointAcceptanceOutcome",
            "CheckpointReobservationClass",
            "CheckpointResumabilityClass",
            "ResultClass",
            "CompletionClassification",
            "EvidenceSufficiencyClassification",
            "ResidualUncertaintyClassification",
            "DegradationClassification",
            "ClosureBasisClassification",
            "TerminalityBasisClassification",
            "AuthoritySourceClass",
        ],
    ),
    (
        "orket.core.domain.orket_manifest",
        [
            "GuardName",
        ],
    ),
    (
        "orket.core.domain.sandbox",
        [
            "SandboxStatus",
            "TechStack",
        ],
    ),
    (
        "orket.core.domain.sandbox_cleanup",
        [
            "DockerResourceType",
        ],
    ),
    (
        "orket.core.domain.sandbox_lifecycle",
        [
            "SandboxState",
            "CleanupState",
            "TerminalReason",
            "LifecycleEvent",
            "OwnershipConfidence",
            "ReconciliationClassification",
        ],
    ),
    (
        "orket.core.domain.workitem_transition",
        [
            "TransitionErrorCode",
        ],
    ),
    (
        "orket.core.types",
        [
            "CardType",
            "CardStatus",
            "WaitReason",
        ],
    ),
    (
        "orket.streaming.model_provider",
        [
            "ProviderEventType",
        ],
    ),
]
ENUM_TYPES = [getattr(import_module(module), name) for module, names in ENUM_SCOPE for name in names]
PUBLIC_REEXPORTS = {
    # CompensationClass is declared publicly but has never been a package reexport.
    "orket.core.domain.control_plane_enums": ("orket.core.domain", {"CompensationClass"}),
    "orket.core.types": ("orket.schema", set()),
    "orket.streaming.model_provider": ("orket.streaming", set()),
}


def _assert_member_contract(enum_type):
    adapter = TypeAdapter(enum_type)
    for member in enum_type.__members__.values():
        text = f"{enum_type.__name__}.{member.name}"
        assert str(member) == text
        assert f"{member}" == text
        assert format(member, ">40") == format(text, ">40")
        assert repr(member) == f"<{text}: {member.value!r}>"
        assert member == member.value
        assert hash(member) == hash(member.value)
        assert enum_type(member.value) is member
        assert json.loads(json.dumps({"value": member})) == {"value": member.value}
        assert adapter.validate_python(member.value) is member
        assert adapter.dump_python(member, mode="json") == member.value
        assert adapter.validate_json(adapter.dump_json(member)) is member


@pytest.mark.parametrize("enum_type", ENUM_TYPES, ids=lambda item: item.__name__)
def test_public_enum_text_and_wire_representations(enum_type):
    _assert_member_contract(enum_type)


@pytest.mark.parametrize("module_name,names", ENUM_SCOPE, ids=[row[0] for row in ENUM_SCOPE])
def test_public_enum_inventory_and_reexport_identity(module_name, names):
    module = import_module(module_name)
    declared = {
        name
        for name, value in vars(module).items()
        if isinstance(value, type)
        and issubclass(value, str)
        and issubclass(value, Enum)
        and value.__module__ == module_name
    }
    assert declared == set(names)
    if module_name in PUBLIC_REEXPORTS:
        public_name, declared_only = PUBLIC_REEXPORTS[module_name]
        public = import_module(public_name)
        for name in set(names) - declared_only:
            assert getattr(public, name) is getattr(module, name)


@pytest.mark.parametrize(
    "model,payload,fields",
    [
        (
            BaseCardConfig,
            {
                "id": "enum-contract",
                "status": CardStatus.DONE,
                "type": CardType.ISSUE,
                "wait_reason": WaitReason.REVIEW,
            },
            ["status", "type", "wait_reason"],
        ),
        (
            TransitionResult,
            {"ok": False, "action": "transition", "error_code": TransitionErrorCode.POLICY_VIOLATION},
            ["error_code"],
        ),
        (ProviderEvent, {"provider_turn_id": "enum-contract", "event_type": ProviderEventType.READY}, ["event_type"]),
    ],
)
def test_public_model_json_keeps_enum_values_and_identity(model, payload, fields):
    instance = model.model_validate(payload)
    wire = json.loads(instance.model_dump_json())
    restored = model.model_validate_json(instance.model_dump_json())
    for field in fields:
        assert getattr(instance, field) is payload[field]
        assert wire[field] == payload[field].value
        assert getattr(restored, field) is payload[field]
