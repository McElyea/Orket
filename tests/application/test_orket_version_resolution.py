from __future__ import annotations

import orket


def test_resolve_runtime_version_prefers_installed_metadata(monkeypatch):
    """Layer: unit. Verifies installed metadata is authoritative for runtime version reporting."""
    monkeypatch.setattr(orket, "version", lambda _package: "9.9.9")

    resolved = orket._resolve_runtime_version()

    assert resolved == "9.9.9"


def test_resolve_runtime_version_uses_pyproject_for_local_dev(monkeypatch):
    """Layer: unit. Verifies local-dev version derives from pyproject metadata when package is not installed."""
    def _raise_not_found(_package):
        raise orket.PackageNotFoundError("orket")

    monkeypatch.setattr(orket, "version", _raise_not_found)
    monkeypatch.setattr(orket, "_read_pyproject_version", lambda: "1.2.3")

    resolved = orket._resolve_runtime_version()

    assert resolved == "1.2.3-local"


def test_resolve_runtime_version_has_safe_local_fallback_when_metadata_missing(monkeypatch):
    """Layer: unit. Verifies deterministic fallback when neither package nor pyproject version is available."""
    def _raise_not_found(_package):
        raise orket.PackageNotFoundError("orket")

    monkeypatch.setattr(orket, "version", _raise_not_found)
    monkeypatch.setattr(orket, "_read_pyproject_version", lambda: None)

    resolved = orket._resolve_runtime_version()

    assert resolved == "0.0.0-local"
