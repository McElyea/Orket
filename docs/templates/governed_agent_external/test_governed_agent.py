from __future__ import annotations

from pathlib import Path

from orket_extension_sdk.validate import validate_extension


def test_template_manifest_and_imports_are_valid() -> None:
    result = validate_extension(
        Path(__file__).parent,
        strict=True,
        include_import_scan=True,
    )

    assert result["ok"] is True
