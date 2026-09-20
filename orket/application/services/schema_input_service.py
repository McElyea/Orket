"""Capture missing authored-asset identities before validating effect-free core values."""
from __future__ import annotations

import json
from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin

from pydantic import AliasChoices, BaseModel
from pydantic.fields import FieldInfo

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.schema import BaseCardConfig, VerificationScenario

ModelT = TypeVar("ModelT", bound=BaseModel)


def _input_key(name: str, field: FieldInfo, payload: dict[str, Any], config: dict[str, Any]) -> str | None:
    alias = field.validation_alias
    choices = alias.choices if isinstance(alias, AliasChoices) else [alias]
    if config.get("validate_by_alias", True):
        for key in choices:
            if isinstance(key, str) and key in payload:
                return key
    allow_name = alias is None or config.get("validate_by_name", config.get("populate_by_name", False))
    return name if allow_name and name in payload else None


def _capture(
    annotation: Any, value: Any, inputs: RuntimeInputService, ancestors: frozenset[int] = frozenset()
) -> Any:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (UnionType, Union):
        members = [item for item in args if item is not type(None)]
        return _capture(members[0], value, inputs, ancestors) if len(members) == 1 else value
    is_model = isinstance(annotation, type) and issubclass(annotation, BaseModel)
    if is_model and annotation.__pydantic_root_model__:
        return _capture(annotation.model_fields["root"].annotation, value, inputs, ancestors)
    typed_list = origin is list and isinstance(value, list)
    typed_dict = origin is dict and isinstance(value, dict)
    if not (typed_list or typed_dict or (is_model and isinstance(value, dict))):
        return value
    if id(value) in ancestors:
        raise ValueError("E_SCHEMA_ASSET_CYCLE")
    ancestors = ancestors | {id(value)}
    if origin is list and isinstance(value, list):
        return [_capture(args[0], item, inputs, ancestors) for item in value]
    if origin is dict and isinstance(value, dict):
        return {key: _capture(args[1], item, inputs, ancestors) for key, item in value.items()}
    payload = dict(value)
    identity = annotation.model_fields.get("id")
    if "id" not in payload and identity is not None and identity.is_required() and identity.validation_alias is None:
        if issubclass(annotation, BaseCardConfig):
            payload["id"] = inputs.create_card_id()
        elif issubclass(annotation, VerificationScenario):
            payload["id"] = inputs.create_verification_scenario_id()
    for name, field in annotation.model_fields.items():
        key = _input_key(name, field, payload, annotation.model_config)
        if key is not None:
            payload[key] = _capture(field.annotation, payload[key], inputs, ancestors)
    return payload


def validate_config_asset(
    model_type: type[ModelT], payload: Any, *, runtime_inputs: RuntimeInputService | None = None
) -> ModelT:
    """Admit an authored value; never use this factory to repair accepted history."""
    inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
    return model_type.model_validate(_capture(model_type, payload, inputs))


def validate_config_asset_json(
    model_type: type[ModelT], raw: str, *, runtime_inputs: RuntimeInputService | None = None
) -> ModelT:
    """Keep Pydantic JSON-mode validation, including its malformed-input errors."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return model_type.model_validate_json(raw)
    inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs
    return model_type.model_validate_json(json.dumps(_capture(model_type, payload, inputs)))
