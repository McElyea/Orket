from __future__ import annotations

from typing import Final


JSON_PARSE_ERROR: Final[str] = "JSON_PARSE_ERROR"
SCHEMA_MISMATCH: Final[str] = "SCHEMA_MISMATCH"
EXTRANEOUS_TEXT: Final[str] = "EXTRANEOUS_TEXT"
TOOL_SHAPE_INVALID: Final[str] = "TOOL_SHAPE_INVALID"
STOP_NOT_HONORED: Final[str] = "STOP_NOT_HONORED"

ERR_JSON_MD_FENCE: Final[str] = "ERR_JSON_MD_FENCE"
ERR_THINK_OVERFLOW: Final[str] = "ERR_THINK_OVERFLOW"
ERR_SCHEMA_EXTRA_KEYS: Final[str] = "ERR_SCHEMA_EXTRA_KEYS"


_FAMILY_BY_LEAF: Final[dict[str, str]] = {
    ERR_JSON_MD_FENCE: EXTRANEOUS_TEXT,
    ERR_THINK_OVERFLOW: EXTRANEOUS_TEXT,
    ERR_SCHEMA_EXTRA_KEYS: SCHEMA_MISMATCH,
}

_FAMILY_DESCRIPTIONS: Final[dict[str, str]] = {
    JSON_PARSE_ERROR: "Payload failed strict JSON parsing.",
    SCHEMA_MISMATCH: "Payload parsed but violated schema contract.",
    EXTRANEOUS_TEXT: "Payload contained markdown/thinking/narrative residue.",
    TOOL_SHAPE_INVALID: "Tool call payload shape was invalid.",
    STOP_NOT_HONORED: "Generation exceeded configured stop conditions.",
}


def all_error_families() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                JSON_PARSE_ERROR,
                SCHEMA_MISMATCH,
                EXTRANEOUS_TEXT,
                TOOL_SHAPE_INVALID,
                STOP_NOT_HONORED,
            }
        )
    )


def all_error_leaf_codes() -> tuple[str, ...]:
    return tuple(sorted(_FAMILY_BY_LEAF.keys()))


def error_family_for_leaf(code: str) -> str:
    return _FAMILY_BY_LEAF.get(str(code or "").strip(), "")


def error_family_description(code: str) -> str:
    key = str(code or "").strip()
    return _FAMILY_DESCRIPTIONS.get(key, "")


def error_registry_snapshot() -> dict[str, object]:
    return {
        "schema_version": "local_prompt_error_registry.v1",
        "families": [
            {"family": family, "description": _FAMILY_DESCRIPTIONS.get(family, "")} for family in all_error_families()
        ],
        "leaf_mappings": [{"leaf_code": leaf, "family": _FAMILY_BY_LEAF[leaf]} for leaf in all_error_leaf_codes()],
    }
