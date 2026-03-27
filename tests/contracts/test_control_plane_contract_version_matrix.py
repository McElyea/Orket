# Layer: contract

from __future__ import annotations

import pytest
from pydantic import BaseModel

from orket.core.contracts import control_plane_models
from orket.core.contracts.control_plane_models import (
    CONTROL_PLANE_CONTRACT_VERSION_V1,
    CONTROL_PLANE_SNAPSHOT_VERSION_V1,
    ResolvedConfigurationSnapshot,
    ResolvedPolicySnapshot,
)


pytestmark = pytest.mark.contract


def _record_model_classes_with_contract_version() -> list[type[BaseModel]]:
    classes: list[type[BaseModel]] = []
    for exported_name in control_plane_models.__all__:
        exported = getattr(control_plane_models, exported_name)
        if not isinstance(exported, type) or not issubclass(exported, BaseModel):
            continue
        if "contract_version" in exported.model_fields:
            classes.append(exported)
    return classes


def test_all_control_plane_record_models_pin_contract_version_v1() -> None:
    models = _record_model_classes_with_contract_version()
    assert models
    for model in models:
        assert model.model_fields["contract_version"].default == CONTROL_PLANE_CONTRACT_VERSION_V1


def test_snapshot_models_pin_snapshot_schema_v1_without_contract_version_field() -> None:
    for snapshot_model in (ResolvedPolicySnapshot, ResolvedConfigurationSnapshot):
        assert "contract_version" not in snapshot_model.model_fields
        assert snapshot_model.model_fields["schema_version"].default == CONTROL_PLANE_SNAPSHOT_VERSION_V1
