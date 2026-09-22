"""Application publication steps over the classified native filesystem adapter."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.storage import kernel_state_store as store
from orket.core.contracts.kernel_triplet import RefSource, iter_link_refs, pointer_token

from .layout import (
    DIR_COMMITTED,
    DIR_STAGING,
    I_REF_MULTISOURCE,
    LSI_VERSION,
    event_line,
    objects_dir,
    objects_path,
    refs_by_id_dir,
    refs_by_id_path,
    root_index,
    scope_root,
    triplets_path,
    write_json,
)


@dataclass(frozen=True, slots=True)
class PromotionPaths:
    committed: Path
    staging: Path
    candidate: Path
    backup: Path

    @classmethod
    def capture(cls, root: str, run_id: str, turn_id: str) -> "PromotionPaths":
        base = root_index(root)
        return cls(
            scope_root(root, DIR_COMMITTED),
            scope_root(root, DIR_STAGING, run_id, turn_id),
            base / f"{DIR_COMMITTED}.__new",
            base / f"{DIR_COMMITTED}.__bak",
        )


def require_unused_candidate(paths: PromotionPaths) -> None:
    for path in (paths.candidate, paths.backup):
        if store.exists(path):
            raise FileExistsError(f"E_KERNEL_PROMOTION_RECOVERY_REQUIRED: {path}")


def seed_candidate(paths: PromotionPaths) -> None:
    if store.exists(paths.committed):
        store.copy_tree(paths.committed, paths.candidate)
    else:
        store.make_directory(paths.candidate)


def copy_staged_objects(paths: PromotionPaths) -> None:
    source = objects_dir(paths.staging)
    if not store.exists(source):
        return
    for path in store.paths(source, "*"):
        if store.is_directory(path):
            continue
        destination = objects_dir(paths.candidate) / path.relative_to(source)
        if not store.exists(destination):
            store.make_directory(destination.parent)
            store.copy_file(path, destination)


def copy_staged_triplets(paths: PromotionPaths, stems: list[str], tombstones: set[str]) -> None:
    for stem in stems:
        source, destination = triplets_path(paths.staging, stem), triplets_path(paths.candidate, stem)
        if stem not in tombstones and store.exists(source):
            store.make_directory(destination.parent)
            store.copy_file(source, destination)


def prune_sources(paths: PromotionPaths, stems: list[str], tombstones: set[str]) -> None:
    directory = refs_by_id_dir(paths.candidate)
    if store.exists(directory):
        for path in sorted(store.paths(directory, "*.json"), key=lambda value: value.as_posix()):
            if not store.is_file(path):
                continue
            record = store.read_json(path)
            if not isinstance(record, dict):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
            sources = record.get("sources")
            if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
            record["sources"] = [source for source in sources if source.get("stem") not in stems]
            record.setdefault("lsi_version", LSI_VERSION)
            write_json(path, record)
    for stem in sorted(tombstones):
        path = triplets_path(paths.candidate, stem)
        if store.exists(path):
            store.remove_file(path)


def collect_sources(
    paths: PromotionPaths, stems: list[str], tombstones: set[str]
) -> dict[tuple[str, str], list[RefSource]]:
    grouped: dict[tuple[str, str], list[RefSource]] = {}
    for stem in stems:
        if stem in tombstones:
            continue
        path = triplets_path(paths.staging, stem)
        record = store.read_json(path)
        digest = record.get("links_digest") if isinstance(record, dict) else None
        if not isinstance(digest, str) or not digest:
            raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
        links = store.read_json(objects_path(paths.staging, digest))
        if not isinstance(links, dict):
            raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
        for kind, identity, location, relationship in iter_link_refs(links):
            refs_by_id_path(paths.candidate, kind, identity)
            grouped.setdefault((kind, identity), []).append(RefSource(stem, location, relationship, digest))
    return grouped


def inject_sources(candidate: Path, grouped: dict[tuple[str, str], list[RefSource]]) -> list[str]:
    events = []
    for (kind, identity), sources in sorted(grouped.items()):
        path = refs_by_id_path(candidate, kind, identity)
        record: dict[str, Any] = {"lsi_version": LSI_VERSION, "type": kind, "id": identity, "sources": []}
        if store.exists(path):
            record = store.read_json(path)
            if not isinstance(record, dict):
                raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
            record.setdefault("lsi_version", LSI_VERSION)
            if record.get("type") is None:
                record["type"] = kind
            if record.get("id") is None:
                record["id"] = identity
        existing = record.get("sources")
        if not isinstance(existing, list) or any(not isinstance(source, dict) for source in existing):
            raise ValueError(f"E_KERNEL_STATE_INDEX_UNAVAILABLE: {path}")
        combined = list(existing)
        combined.extend(
            dict(
                stem=source.stem,
                location=source.location,
                relationship=source.relationship,
                artifact_digest=source.artifact_digest,
            )
            for source in sources
        )
        record["sources"] = sorted(
            (source for source in combined if isinstance(source, dict)),
            key=lambda source: tuple(
                str(source.get(key) or "") for key in ("stem", "location", "relationship", "artifact_digest")
            ),
        )
        write_json(path, record)
        if len(record["sources"]) > 1:
            stems = sorted({str(source.get("stem") or "") for source in record["sources"]})
            events.append(
                event_line(
                    "INFO",
                    "promotion",
                    I_REF_MULTISOURCE,
                    f"/index/refs/by_id/{pointer_token(kind)}/{pointer_token(identity)}",
                    "Multiple stems reference the same {type,id}.",
                    type=kind,
                    id=identity,
                    stems=stems,
                )
            )
    return events


def replace_candidate(paths: PromotionPaths) -> None:
    if store.exists(paths.committed):
        store.replace(paths.committed, paths.backup)
    store.replace(paths.candidate, paths.committed)


def cleanup_success(paths: PromotionPaths) -> None:
    if store.exists(paths.backup):
        store.remove_tree(paths.backup)
    if store.exists(paths.staging):
        store.remove_tree(paths.staging)
