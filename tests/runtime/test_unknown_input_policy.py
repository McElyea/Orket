from __future__ import annotations

import pytest

from orket.runtime.unknown_input_policy import (
    unknown_input_policy_snapshot,
    validate_allowed_token,
)


# Layer: unit
def test_unknown_input_policy_snapshot_includes_provider_surface() -> None:
    payload = unknown_input_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    surfaces = payload["surfaces"]
    provider = next(
        row for row in surfaces if row["surface"] == "provider_runtime_target.requested_provider"
    )
    assert provider["on_unknown"] == "fail_closed"
    assert provider["error_code"] == "E_UNKNOWN_PROVIDER_INPUT"


# Layer: contract
def test_validate_allowed_token_accepts_known_token_case_insensitive() -> None:
    assert validate_allowed_token(
        token="Ollama",
        allowed=("ollama", "openai_compat"),
        error_code_prefix="E_UNKNOWN_PROVIDER_INPUT",
    ) == "ollama"


# Layer: contract
def test_validate_allowed_token_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="E_UNKNOWN_PROVIDER_INPUT:unknown"):
        _ = validate_allowed_token(
            token="unknown",
            allowed=("ollama", "openai_compat"),
            error_code_prefix="E_UNKNOWN_PROVIDER_INPUT",
        )
