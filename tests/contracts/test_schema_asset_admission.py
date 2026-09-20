"""Application identity capture and core/JSON validation boundary contracts."""
from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from pydantic import AliasPath, BaseModel, ConfigDict, Field, RootModel, ValidationError

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.schema_input_service import validate_config_asset, validate_config_asset_json
from orket.schema import BaseCardConfig, CardDetail, EpicConfig, IssueConfig, TeamConfig

pytestmark = pytest.mark.contract


class ObservedIdentities(RuntimeInputService):
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def _next(self, kind):
        self.calls.append(kind)
        if self.fail:
            raise OSError("identity source unavailable")
        return f"{kind}-{len(self.calls)}"

    def create_card_id(self):
        return self._next("card")

    def create_verification_scenario_id(self):
        return self._next("scenario")


@pytest.mark.parametrize("alias", ["issues", "stories", "cards"])
def test_nested_aliases_capture_ids_without_mutating_authored_payload(alias):
    payload = {"team": "team", "environment": "dev", alias: [{"summary": "Issue", "verification": {
        "scenarios": [{"description": "Check", "input_data": {}, "expected_output": True}]}}]}
    before, inputs = deepcopy(payload), ObservedIdentities()
    value = validate_config_asset(EpicConfig, payload, runtime_inputs=inputs)
    assert inputs.calls == ["card", "card", "scenario"]
    assert value.id == "card-1" and value.issues[0].id == "card-2"
    assert value.issues[0].verification.scenarios[0].id == "scenario-3"
    assert payload == before
    assert EpicConfig.model_validate(value.model_dump()).model_dump() == value.model_dump()


def test_role_maps_and_recursive_card_children_use_declared_model_types():
    inputs = ObservedIdentities()
    team = validate_config_asset(TeamConfig, {"name": "team", "seats": {}, "roles": {
        "builder": {"description": "Build", "params": {"id": None, "children": [{}]}}}}, runtime_inputs=inputs)
    tree = validate_config_asset(CardDetail, {"children": [{"children": [{}]}]}, runtime_inputs=inputs)
    assert team.roles["builder"].id == "card-1"
    assert team.roles["builder"].params == {"id": None, "children": [{}]}
    assert (tree.id, tree.children[0].id, tree.children[0].children[0].id) == ("card-2", "card-3", "card-4")


@pytest.mark.parametrize("identifier", ["retained", ""])
def test_explicit_identity_never_calls_generator(identifier):
    inputs = ObservedIdentities(fail=True)
    value = validate_config_asset(IssueConfig, {"id": identifier}, runtime_inputs=inputs)
    assert value.id == identifier and inputs.calls == []


def test_explicit_invalid_identity_is_rejected_not_replaced():
    inputs = ObservedIdentities()
    with pytest.raises(ValidationError):
        validate_config_asset(IssueConfig, {"id": None}, runtime_inputs=inputs)
    assert inputs.calls == []


def test_identity_failure_is_not_replaced_with_another_source():
    inputs, payload = ObservedIdentities(fail=True), {"summary": "Authored"}
    with pytest.raises(OSError, match="identity source unavailable"):
        validate_config_asset(IssueConfig, payload, runtime_inputs=inputs)
    assert payload == {"summary": "Authored"} and inputs.calls == ["card"]


def test_selected_alias_does_not_generate_for_ignored_issue_payload():
    inputs = ObservedIdentities()
    value = validate_config_asset(EpicConfig, {"id": "epic", "team": "t", "environment": "e",
        "issues": [{"id": "selected"}], "stories": [{}]}, runtime_inputs=inputs)
    assert [issue.id for issue in value.issues] == ["selected"] and inputs.calls == []


def test_json_mode_keeps_strict_date_acceptance():
    class StrictDate(BaseModel):
        model_config = ConfigDict(strict=True)
        day: date

    value = validate_config_asset_json(StrictDate, '{"day":"2026-09-20"}')
    assert value == StrictDate.model_validate_json('{"day":"2026-09-20"}')


def test_malformed_json_keeps_native_validation_error():
    with pytest.raises(ValidationError) as native:
        IssueConfig.model_validate_json('{broken')
    with pytest.raises(ValidationError) as admitted:
        validate_config_asset_json(IssueConfig, '{broken')
    assert admitted.value.errors() == native.value.errors()


def test_custom_identity_alias_is_not_guessed():
    class AliasedCard(BaseCardConfig):
        id: str = Field(validation_alias=AliasPath("identity", "value"))

    inputs = ObservedIdentities(fail=True)
    assert validate_config_asset(AliasedCard, {"identity": {"value": "retained"}}, runtime_inputs=inputs).id == "retained"
    with pytest.raises(ValidationError):
        validate_config_asset(AliasedCard, {}, runtime_inputs=inputs)
    assert inputs.calls == []


def test_ambiguous_model_union_does_not_guess_an_identity():
    class Envelope(BaseModel):
        payload: IssueConfig | CardDetail

    inputs = ObservedIdentities(fail=True)
    with pytest.raises(ValidationError):
        validate_config_asset(Envelope, {"payload": {}}, runtime_inputs=inputs)
    assert inputs.calls == []


def test_root_model_dictionary_preserves_typed_admission():
    inputs = ObservedIdentities()
    value = validate_config_asset(RootModel[dict[str, IssueConfig]], {"item": {}}, runtime_inputs=inputs)
    assert value.root["item"].id == "card-1" and inputs.calls == ["card"]


def test_cyclic_schema_object_is_rejected_without_unbounded_identity_generation():
    payload = {"children": []}
    payload["children"].append(payload)
    inputs = ObservedIdentities()
    with pytest.raises(ValueError, match="E_SCHEMA_ASSET_CYCLE"):
        validate_config_asset(CardDetail, payload, runtime_inputs=inputs)
    assert inputs.calls == ["card"]


def test_repeated_object_is_admitted_at_each_distinct_tree_position():
    shared, inputs = {}, ObservedIdentities()
    value = validate_config_asset(CardDetail, {"children": [shared, shared]}, runtime_inputs=inputs)
    assert [item.id for item in value.children] == ["card-2", "card-3"]
    assert shared == {}


def test_declared_subclass_identity_default_is_preserved():
    class NamedCard(BaseCardConfig):
        id: str = "declared"

    inputs = ObservedIdentities(fail=True)
    assert validate_config_asset(NamedCard, {}, runtime_inputs=inputs).id == "declared"
    assert inputs.calls == []
