"""Application settings reads, verified publication and resumable preference migration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.storage.settings_file_store import (
    hold_settings_files,
    read_settings_document,
    retire_legacy_settings,
    write_settings_document,
)
from orket.core.contracts.local_file_lock import LocalFileLockError
from orket.core.contracts.protocol_hashing import canonical_json
from orket.runtime_paths import resolve_user_preferences_path, resolve_user_settings_path

_MARKER = "legacy_model_preferences_v1"
_PENDING = "legacy_model_preferences_pending_v1"


@dataclass(frozen=True)
class SettingsLocation:
    invocation_root: Path
    durable_root: str
    settings_override: Path | None = None
    preferences_override: Path | None = None

    def resolve(self) -> tuple[Path, Path, Path | None]:
        options = {"invocation_root": self.invocation_root, "environment": {"ORKET_DURABLE_ROOT": self.durable_root},
                   "create_parent": False}
        settings = resolve_user_settings_path(self.settings_override, migrate_legacy=False, **options)
        preferences = resolve_user_preferences_path(self.preferences_override, **options)
        if settings == preferences:
            raise ValueError("E_SETTINGS_PATHS_MUST_DIFFER")
        legacy = self.invocation_root / "user_settings.json" if self.settings_override is None else None
        return settings, preferences, legacy if legacy != settings else None


class SettingsUpdateConflict(ValueError):
    """A conditional settings write cannot adopt the caller's observed input."""


class UserSettingsService:
    """One captured location per operation; no hidden data or selected-path cache."""

    def __init__(self, location: SettingsLocation):
        self.settings, self.preferences, self.legacy = location.resolve()
        self.paths = (self.settings, self.preferences)

    def read_settings(self) -> dict[str, Any]:
        observed = read_settings_document(self.settings)
        if observed is not None or self.legacy is None:
            return observed or {}
        if read_settings_document(self.legacy) is None:
            return {}
        with hold_settings_files(self.paths):
            return self._read_settings_locked()

    def _read_settings_locked(self) -> dict[str, Any]:
        observed = read_settings_document(self.settings)
        if observed is not None or self.legacy is None:
            return observed or {}
        legacy = read_settings_document(self.legacy)
        if legacy is None:
            return {}
        # Only an actual legacy migration needs its separate native owner.
        with hold_settings_files((self.legacy,)):
            legacy = read_settings_document(self.legacy)
            if legacy is None:
                return {}
            write_settings_document(self.settings, legacy)
            retire_legacy_settings(self.legacy, legacy)
            return legacy

    def save(
        self, payload: dict[str, Any], *, preferences: bool, expected_settings: dict[str, Any] | None = None,
    ) -> None:
        try:
            with hold_settings_files(self.paths):
                existing = read_settings_document(self.preferences) or {}
                if _PENDING in _metadata(existing):
                    raise ValueError("E_SETTINGS_MIGRATION_PENDING: load preferences to resume first")
                if preferences and _PENDING in _metadata(payload):
                    raise ValueError("E_SETTINGS_MIGRATION_MARKER_RESERVED")
                if expected_settings is not None:
                    current = read_settings_document(self.settings) or {}
                    if canonical_json(current) != canonical_json(expected_settings):
                        raise SettingsUpdateConflict("E_SETTINGS_CHANGED: reload before retry")
                write_settings_document(self.preferences if preferences else self.settings, payload)
        except LocalFileLockError as exc:
            if expected_settings is not None and str(exc).endswith(":owner_busy"):
                raise SettingsUpdateConflict("E_SETTINGS_BUSY: reload before retry") from exc
            raise

    def update(self, key: str, value: Any) -> None:
        with hold_settings_files(self.paths):
            preferences = read_settings_document(self.preferences) or {}
            if _PENDING in _metadata(preferences):
                raise ValueError("E_SETTINGS_MIGRATION_PENDING: load preferences to resume first")
            settings = self._read_settings_locked()
            settings[key] = value
            write_settings_document(self.settings, settings)

    def read_preferences(self) -> dict[str, Any]:
        with hold_settings_files(self.paths):
            settings = self._read_settings_locked()
            preferences = read_settings_document(self.preferences) or {}
            meta = _metadata(preferences, create=True)
            pending = meta.get(_PENDING)
            if _PENDING not in meta:
                legacy = {k: v for k, v in settings.items() if k.startswith("preferred_") and k[10:].strip()
                          and str(v or "").strip()}
                markers = meta.setdefault("migration_markers", {})
                if not isinstance(markers, dict):
                    raise ValueError("E_SETTINGS_MIGRATION_MARKERS_INVALID")
                if markers.get(_MARKER) and not legacy:
                    return preferences
                models = preferences.setdefault("models", {})
                if not isinstance(models, dict):
                    raise ValueError("E_SETTINGS_MODELS_INVALID")
                desired = {k[10:].strip(): str(v).strip() for k, v in legacy.items()}
                if markers.get(_MARKER) and any(models.get(k) != v for k, v in desired.items()):
                    raise ValueError("E_SETTINGS_LEGACY_MIGRATION_CONFLICT")
                models.update(desired)
                pending = {"settings_path": str(self.settings), "values": legacy}
                meta[_PENDING] = pending
                write_settings_document(self.preferences, preferences)
            self._finish_migration(settings, preferences, pending)
            return preferences

    def _finish_migration(self, settings: dict[str, Any], preferences: dict[str, Any], pending: Any) -> None:
        if (not isinstance(pending, dict) or pending.get("settings_path") != str(self.settings)
                or not isinstance(pending.get("values"), dict)):
            raise ValueError("E_SETTINGS_MIGRATION_BINDING_INVALID")
        values = pending["values"]
        models = preferences.get("models")
        meta = _metadata(preferences)
        markers = meta.setdefault("migration_markers", {})
        if not isinstance(markers, dict) or not isinstance(models, dict):
            raise ValueError("E_SETTINGS_MIGRATION_BINDING_INVALID")
        if any(not k.startswith("preferred_") or not k[10:].strip() or not str(v or "").strip()
               or models.get(k[10:].strip()) != str(v).strip()
               or (k in settings and canonical_json(settings[k]) != canonical_json(v)) for k, v in values.items()):
            raise ValueError("E_SETTINGS_LEGACY_MIGRATION_CONFLICT")
        if any(k in settings for k in values):
            for key in values:
                settings.pop(key, None)
            write_settings_document(self.settings, settings)
        markers[_MARKER] = True
        del meta[_PENDING]
        write_settings_document(self.preferences, preferences)


def _metadata(preferences: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    meta = preferences.setdefault("_meta", {}) if create else preferences.get("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError("E_SETTINGS_METADATA_INVALID")
    return meta
