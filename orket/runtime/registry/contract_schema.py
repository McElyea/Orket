from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContractRegistry:
    """Shared validation for simple row-oriented runtime contracts."""

    schema_version: str
    rows: list[dict[str, Any]]
    collection_key: str
    row_id_field: str
    empty_error: str
    row_schema_error: str
    row_id_required_error: str
    duplicate_error: str
    required_ids: set[str] | None = None
    required_set_error: str | None = None
    required_row_fields: tuple[str, ...] = ()
    field_required_errors: dict[str, str] = field(default_factory=dict)
    allowed_row_values: dict[str, set[str]] = field(default_factory=dict)
    field_allowed_errors: dict[str, str] = field(default_factory=dict)

    def validate(self, payload: dict[str, Any] | None = None) -> tuple[str, ...]:
        resolved_payload = dict(
            payload
            or {
                "schema_version": self.schema_version,
                self.collection_key: [dict(row) for row in self.rows],
            }
        )
        rows = list(resolved_payload.get(self.collection_key) or [])
        if not rows:
            raise ValueError(self.empty_error)

        observed_ids: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(self.row_schema_error)
            row_id = _normalize_token(row.get(self.row_id_field))
            if not row_id:
                raise ValueError(self.row_id_required_error)

            for field_name in self.required_row_fields:
                field_value = _normalize_token(row.get(field_name))
                if not field_value:
                    error_code = self.field_required_errors.get(field_name) or f"E_{field_name.upper()}_REQUIRED"
                    raise ValueError(f"{error_code}:{row_id}")
                allowed_values = self.allowed_row_values.get(field_name)
                if allowed_values is not None and field_value.lower() not in {
                    value.lower() for value in allowed_values
                }:
                    error_code = self.field_allowed_errors.get(field_name) or f"E_{field_name.upper()}_INVALID"
                    raise ValueError(f"{error_code}:{row_id}")

            observed_ids.append(row_id)

        if len(set(observed_ids)) != len(observed_ids):
            raise ValueError(self.duplicate_error)
        if self.required_ids is not None and {token for token in observed_ids} != set(self.required_ids):
            raise ValueError(self.required_set_error or "E_CONTRACT_REQUIRED_ID_SET_MISMATCH")
        return tuple(sorted(observed_ids))


def _normalize_token(value: Any) -> str:
    return str(value or "").strip()
