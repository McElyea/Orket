from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .manifest import PackMetadata

_SYSTEM_CANDIDATES = ("system.txt", "system.md")
_REQUIRED_FILENAMES = ("pack.json", "constraints.yaml")


class PackValidationError(ValueError):
    """Deterministic pack validation error."""


@dataclass(frozen=True)
class ResolvedPack:
    metadata: PackMetadata
    inheritance_chain: tuple[Path, ...]
    resolved_files: dict[str, str]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackValidationError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise PackValidationError(f"Expected object in JSON file: {path}")
    return payload


def _resolve_system_file(pack_dir: Path) -> str:
    existing = [name for name in _SYSTEM_CANDIDATES if (pack_dir / name).is_file()]
    if not existing:
        raise PackValidationError(f"Missing required system prompt file in pack: {pack_dir}")
    return sorted(existing)[0]


def _validate_pack_dir(pack_dir: Path) -> None:
    if not pack_dir.is_dir():
        raise PackValidationError(f"Pack path is not a directory: {pack_dir}")
    missing = [name for name in _REQUIRED_FILENAMES if not (pack_dir / name).is_file()]
    if missing:
        joined = ", ".join(sorted(missing))
        raise PackValidationError(f"Missing required pack files ({joined}) in: {pack_dir}")
    _resolve_system_file(pack_dir)


def _load_pack_metadata(pack_dir: Path) -> PackMetadata:
    payload = _read_json(pack_dir / "pack.json")
    pack_id = str(payload.get("id") or "").strip()
    pack_version = str(payload.get("version") or "").strip()
    extends_raw = payload.get("extends")
    extends = str(extends_raw).strip() if extends_raw is not None else None
    if not pack_id:
        raise PackValidationError(f"pack.json missing non-empty 'id' in: {pack_dir}")
    if not pack_version:
        raise PackValidationError(f"pack.json missing non-empty 'version' in: {pack_dir}")
    return PackMetadata(pack_id=pack_id, pack_version=pack_version, extends=extends or None, path=pack_dir)


def _resolve_extends_path(*, extends: str, current_path: Path, packs_root: Path | None) -> Path:
    candidate = Path(extends)
    if candidate.is_absolute():
        return candidate
    if "/" in extends or "\\" in extends or extends.startswith("."):
        return (current_path.parent / candidate).resolve()
    if packs_root is None:
        raise PackValidationError(
            f"Pack extends value '{extends}' requires packs_root for id-based resolution: {current_path}"
        )
    return (packs_root / extends).resolve()


def _collect_file_content(pack_dir: Path) -> dict[str, str]:
    contents: dict[str, str] = {}
    system_name = _resolve_system_file(pack_dir)
    for file_name in (system_name, "constraints.yaml", "developer.txt", "examples.jsonl"):
        target = pack_dir / file_name
        if target.is_file():
            contents[file_name] = target.read_text(encoding="utf-8")
    return contents


def resolve_pack(pack_path: Path, *, packs_root: Path | None = None) -> ResolvedPack:
    resolved_pack_path = pack_path.resolve()
    chain: list[Path] = []
    seen: set[Path] = set()

    def _walk(current: Path) -> None:
        if current in seen:
            raise PackValidationError(f"Detected cyclic pack inheritance at: {current}")
        seen.add(current)
        _validate_pack_dir(current)
        metadata = _load_pack_metadata(current)
        if metadata.extends:
            parent = _resolve_extends_path(extends=metadata.extends, current_path=current, packs_root=packs_root)
            _walk(parent)
        chain.append(current)

    _walk(resolved_pack_path)

    merged_files: dict[str, str] = {}
    last_metadata: PackMetadata | None = None
    for current in chain:
        _validate_pack_dir(current)
        metadata = _load_pack_metadata(current)
        last_metadata = metadata
        current_files = _collect_file_content(current)
        for name, content in current_files.items():
            # Child overlays parent by file name.
            merged_files[name] = content
        current_system = next((name for name in _SYSTEM_CANDIDATES if name in current_files), None)
        if current_system is not None:
            for other in _SYSTEM_CANDIDATES:
                if other != current_system:
                    merged_files.pop(other, None)

    if last_metadata is None:
        raise PackValidationError(f"Unable to resolve pack: {pack_path}")

    normalized = {name: merged_files[name] for name in sorted(merged_files)}
    return ResolvedPack(metadata=last_metadata, inheritance_chain=tuple(chain), resolved_files=normalized)


def write_resolved_pack(resolved: ResolvedPack, out_dir: Path) -> Path:
    target = out_dir.resolve()
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for name, content in resolved.resolved_files.items():
        (target / name).write_text(content, encoding="utf-8")
    pack_payload = {
        "id": resolved.metadata.pack_id,
        "version": resolved.metadata.pack_version,
        "extends": resolved.metadata.extends,
        "resolved_inheritance_chain": [
            str(path).replace("\\", "/") for path in resolved.inheritance_chain
        ],
    }
    (target / "pack.json").write_text(json.dumps(pack_payload, indent=2) + "\n", encoding="utf-8")
    return target
