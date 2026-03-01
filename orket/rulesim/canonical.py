from __future__ import annotations

import hashlib
import json
import math
from typing import Any


class StateSerializationError(ValueError):
    pass


def _float_to_sig6(value: float) -> float:
    if not math.isfinite(value):
        raise StateSerializationError("non-finite float values are not supported")
    return float(format(value, ".6g"))


def normalize_for_json(value: Any, *, path: str = "state") -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _float_to_sig6(value)
    if isinstance(value, list):
        return [normalize_for_json(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, tuple):
        return [normalize_for_json(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StateSerializationError(f'{path} contains non-string key type "{type(key).__name__}"')
            normalized[key] = normalize_for_json(item, path=f'{path}["{key}"]')
        return normalized
    raise StateSerializationError(f'{path} is non-serializable type "{type(value).__name__}"')


def canonical_json(value: Any, *, root_path: str = "value") -> str:
    normalized = normalize_for_json(value, path=root_path)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_state(state_dict: dict[str, Any]) -> str:
    payload = canonical_json(state_dict, root_path="state").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
