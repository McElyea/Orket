from __future__ import annotations

from pathlib import Path

from orket.interfaces.prompts_cli import resolve_prompt


def test_canonical_prompt_resolution_from_repo_assets() -> None:
    resolved = resolve_prompt(
        Path("."),
        role="architect",
        dialect="generic",
        selection_policy="stable",
        strict=True,
    )
    metadata = resolved["metadata"]
    layers = resolved["layers"]

    assert metadata["prompt_id"] == "role.architect+dialect.generic"
    assert metadata["selection_policy"] == "stable"
    assert metadata["role_status"] in {"stable", "candidate", "canary"}
    assert metadata["dialect_status"] in {"stable", "candidate", "canary"}
    assert layers["role_base"]["name"] == "architect"
    assert layers["dialect_adapter"]["name"] == "generic"
