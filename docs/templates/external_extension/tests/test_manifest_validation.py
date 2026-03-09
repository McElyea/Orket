from __future__ import annotations

from pathlib import Path

from orket_extension_sdk.validate import validate_extension


def test_template_manifest_validates() -> None:
    result = validate_extension(Path("."))
    assert result["ok"] is True
    assert result["error_count"] == 0
