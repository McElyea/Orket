from __future__ import annotations

from pathlib import Path


def test_sdk_versioning_docs_define_core_compatibility_sla() -> None:
    """Layer: contract. Verifies SDK versioning has a concrete core compatibility window."""
    versioning = Path("docs/requirements/sdk/VERSIONING.md").read_text(encoding="utf-8")
    readme = Path("orket_extension_sdk/README.md").read_text(encoding="utf-8")

    assert "does not follow the core engine version" in versioning
    assert "SDK `0.Y.Z` is compatible with Orket core `0.Y.*` through `0.(Y+2).*`" in versioning
    assert "SDK `0.Y.Z` is compatible with Orket core `0.Y.*` through `0.(Y+2).*`" in readme
