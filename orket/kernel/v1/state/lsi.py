# orket/kernel/v1/lsi.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .canonical import canonical_json_bytes, structural_digest, sorted_deterministically
from .contracts import KernelIssue

# ----------------------------
# Spec-002 constants (minimal)
# ----------------------------

LSI_VERSION = "lsi/v1"

# Directory names (fixed)
DIR_INDEX = "index"
DIR_COMMITTED = "committed"
DIR_STAGING = "staging"
DIR_OBJECTS = "objects"
DIR_TRIPLETS = "triplets"
DIR_REFS = "refs"
DIR_BY_ID = "by_id"

# Error/Info codes used by minimal LSI behaviors
E_RELATIONSHIP_ORPHAN = "E_RELATIONSHIP_ORPHAN"
I_REF_MULTISOURCE = "I_REF_MULTISOURCE"


# ----------------------------
# Data helpers
# ----------------------------

@dataclass(frozen=True)
class TripletDigests:
    dto_type: str | None
    body_digest: str
    links_digest: str
    manifest_digest: str


@dataclass(frozen=True)
class RefSource:
    stem: str
    location: str  # RFC6901 pointer to the ref object (or to its /id)
    relationship: str | None
    artifact_digest: str  # typically links_digest


def _pointer_token(value: str) -> str:
    # RFC6901 escaping: ~ then /
    return value.replace("~", "~0").replace("/", "~1")


def _fs_token(value: str) -> str:
    """
    Deterministic filesystem-safe token.
    - Uses URL percent-encoding for non-safe chars.
    - Keeps common safe characters unescaped.
    Note: Windows forbids ':' in filenames; percent-encoding avoids that.
    """
    return quote(value, safe="-_.~abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def _atomic_write_json(path: Path, obj: Any) -> None:
    _atomic_write_bytes(path, canonical_json_bytes(obj))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_ref_object(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("type"), str) and isinstance(value.get("id"), str)


def _iter_refs_from_links(links: dict[str, Any]) -> Iterable[tuple[str, str, str, str | None]]:
    """
    Yield (ref_type, ref_id, pointer_to_ref_obj, relationship) for every ref object in /links.
    pointer_to_ref_obj is rooted at /links.
    """
    for key in sorted(links.keys()):
        val = links[key]
        key_ptr = f"/links/{_pointer_token(key)}"

        if isinstance(val, list):
            for idx, item in enumerate(val):
                if not _is_ref_object(item):
                    continue
                ptr = f"{key_ptr}/{idx}"
                yield (item["type"], item["id"], ptr, item.get("relationship") if isinstance(item.get("relationship"), str) else None)
        elif _is_ref_object(val):
            yield (val["type"], val["id"], key_ptr, val.get("relationship") if isinstance(val.get("relationship"), str) else None)
        else:
            # Not a ref container (minimal LSI doesn't validate shapes here)
            continue


# ----------------------------
# LSI path layout
# ----------------------------

def _root_index(root: str) -> Path:
    return Path(root) / DIR_INDEX


def _scope_root(root: str, scope: str, run_id: str | None = None, turn_id: str | None = None) -> Path:
    """
    scope in {"committed", "staging"}.
    staging is namespaced by run_id/turn_id.
    """
    base = _root_index(root)
    if scope == DIR_COMMITTED:
        return base / DIR_COMMITTED
    if scope == DIR_STAGING:
        if not run_id or not turn_id:
            raise ValueError("staging scope requires run_id and turn_id")
        return base / DIR_STAGING / _fs_token(run_id) / _fs_token(turn_id)
    raise ValueError(f"unknown scope: {scope}")


def _objects_dir(scope_root: Path) -> Path:
    return scope_root / DIR_OBJECTS


def _objects_path(scope_root: Path, digest_hex: str) -> Path:
    # content-addressed: objects/<prefix>/<digest>
    prefix = digest_hex[:2]
    return _objects_dir(scope_root) / prefix / digest_hex


def _triplets_path(scope_root: Path, stem: str) -> Path:
    # mirror stem as directories: triplets/data/dto/foo/bar.json
    # stem is expected to be normalized with forward slashes.
    return (scope_root / DIR_TRIPLETS / Path(stem)).with_suffix(".json")


def _refs_by_id_path(scope_root: Path, ref_type: str, ref_id: str) -> Path:
    return (scope_root / DIR_REFS / DIR_BY_ID / _fs_token(ref_type) / f"{_fs_token(ref_id)}.json")


# ----------------------------
# Public minimal LSI API
# ----------------------------

class LocalSovereignIndex:
    """
    Minimal Spec-002 LSI v1 implementation.
    This file intentionally focuses on:
      - disk anatomy
      - canonicalization + structural digest
      - staging/committed scopes
      - refs/by_id symbol table (non-owning, multi-source)
      - link integrity lookup (orphan detection) with Self > Staging > Committed order

    Promotion/pruning across scopes belongs in promotion.py, but we DO perform
    stem-scoped pruning within the SAME scope on update to prevent duplicates.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    # ---------- Write paths (staging) ----------

    def stage_triplet(
        self,
        *,
        run_id: str,
        turn_id: str,
        stem: str,
        body: dict[str, Any],
        links: dict[str, Any],
        manifest: dict[str, Any],
    ) -> TripletDigests:
        """
        Write triplet artifacts and index records into staging.
        - Stores canonical bytes in objects/ by digest.
        - Writes triplet record under triplets/<stem>.json
        - Updates refs/by_id records (non-owning, stem-scoped pruning within staging)
        """
        stem = stem.replace("\\", "/").strip("/")

        scope_root = _scope_root(self.root, DIR_STAGING, run_id, turn_id)

        body_bytes = canonical_json_bytes(body)
        links_bytes = canonical_json_bytes(links)
        manifest_bytes = canonical_json_bytes(manifest)

        body_digest = structural_digest(body_bytes)
        links_digest = structural_digest(links_bytes)
        manifest_digest = structural_digest(manifest_bytes)

        # Persist content-addressed objects
        self._put_object(scope_root, body_digest, body_bytes)
        self._put_object(scope_root, links_digest, links_bytes)
        self._put_object(scope_root, manifest_digest, manifest_bytes)

        dto_type = None
        if isinstance(body.get("dto_type"), str):
            dto_type = body["dto_type"].strip().lower()

        record = {
            "lsi_version": LSI_VERSION,
            "stem": stem,
            "dto_type": dto_type,
            "body_digest": body_digest,
            "links_digest": links_digest,
            "manifest_digest": manifest_digest,
            "updated_at_turn": turn_id,
        }
        _atomic_write_json(_triplets_path(scope_root, stem), record)

        # Update refs/by_id for all refs in /links
        sources = []
        for ref_type, ref_id, ptr, relationship in _iter_refs_from_links(links):
            sources.append(
                RefSource(
                    stem=stem,
                    location=ptr,
                    relationship=relationship,
                    artifact_digest=links_digest,
                )
            )

        self._update_refs_by_id(scope_root, sources)

        return TripletDigests(
            dto_type=dto_type,
            body_digest=body_digest,
            links_digest=links_digest,
            manifest_digest=manifest_digest,
        )

    # ---------- Read helpers (tests + kernel) ----------

    def read_triplet_record(self, *, scope: str, stem: str, run_id: str | None = None, turn_id: str | None = None) -> dict[str, Any] | None:
        stem = stem.replace("\\", "/").strip("/")
        scope_root = _scope_root(self.root, scope, run_id, turn_id) if scope == DIR_STAGING else _scope_root(self.root, scope)
        path = _triplets_path(scope_root, stem)
        if not path.exists():
            return None
        return _read_json(path)

    def read_refs_sources(
        self,
        *,
        scope: str,
        ref_type: str,
        ref_id: str,
        run_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        scope_root = _scope_root(self.root, scope, run_id, turn_id) if scope == DIR_STAGING else _scope_root(self.root, scope)
        path = _refs_by_id_path(scope_root, ref_type, ref_id)
        if not path.exists():
            return []
        data = _read_json(path)
        sources = data.get("sources")
        if not isinstance(sources, list):
            return []
        # Return exactly as stored (already canonicalized & sorted)
        return [s for s in sources if isinstance(s, dict)]

    # ---------- Validation (link integrity) ----------

    def validate_links_against_index(
        self,
        *,
        run_id: str,
        turn_id: str,
        stem: str,
    ) -> tuple[str, list[KernelIssue], list[str]]:
        """
        Minimal link integrity law:
          - Extract all {type,id} from /links for the staged stem.
          - Check visibility layers in strict order:
              1) Self   (staging refs where source.stem == stem)
              2) Staging (any staging refs)
              3) Committed (any committed refs)
          - Missing => FAIL E_RELATIONSHIP_ORPHAN at pointer to /id
        Returns (outcome, issues, events)
        """
        stem = stem.replace("\\", "/").strip("/")
        events: list[str] = []

        # Load staged triplet record
        staged_root = _scope_root(self.root, DIR_STAGING, run_id, turn_id)
        triplet = self.read_triplet_record(scope=DIR_STAGING, stem=stem, run_id=run_id, turn_id=turn_id)
        if not triplet:
            issues = [
                KernelIssue(
                    level="FAIL",
                    stage="relationship_vocabulary",
                    code=E_RELATIONSHIP_ORPHAN,
                    location="/ci/schema",
                    message="Triplet not found in staging for validation.",
                    details={"stem": stem, "run_id": run_id, "turn_id": turn_id},
                )
            ]
            events.append(_event_line("FAIL", "relationship_vocabulary", E_RELATIONSHIP_ORPHAN, "/ci/schema", "Triplet missing in staging.", stem=stem))
            return "FAIL", issues, events

        links_digest = triplet.get("links_digest")
        if not isinstance(links_digest, str):
            issues = [
                KernelIssue(
                    level="FAIL",
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/manifest",
                    message="Triplet record missing links_digest.",
                    details={"stem": stem},
                )
            ]
            events.append(_event_line("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/manifest", "Triplet record missing links_digest.", stem=stem))
            return "FAIL", issues, events

        links_obj = self._get_object_json(staged_root, links_digest)
        if not isinstance(links_obj, dict):
            issues = [
                KernelIssue(
                    level="FAIL",
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_LINKS_VALUE",
                    location="/links",
                    message="Links object must be a JSON object.",
                    details={"stem": stem},
                )
            ]
            events.append(_event_line("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_LINKS_VALUE", "/links", "Links object must be a JSON object.", stem=stem))
            return "FAIL", issues, events

        # Evaluate refs deterministically in pointer order
        refs = list(_iter_refs_from_links(links_obj))
        refs.sort(key=lambda r: (r[2], r[0], r[1]))  # pointer, type, id

        issues: list[KernelIssue] = []
        for ref_type, ref_id, ptr, relationship in refs:
            id_ptr = f"{ptr}/id"
            found_layer = self._lookup_ref_visibility(run_id, turn_id, stem, ref_type, ref_id)

            if not found_layer:
                issues.append(
                    KernelIssue(
                        level="FAIL",
                        stage="relationship_vocabulary",
                        code=E_RELATIONSHIP_ORPHAN,
                        location=id_ptr,
                        message="Reference target not found in Self/Staging/Committed visibility.",
                        details={"type": ref_type, "id": ref_id, "relationship": relationship},
                    )
                )
            else:
                events.append(_event_line("INFO", "relationship_vocabulary", "I_REF_VISIBLE", id_ptr, "Reference target resolved.", layer=found_layer, type=ref_type, id=ref_id))

        # Deterministic issue ordering (stage fixed, then pointer, then code, then details)
        issues.sort(key=lambda i: (i.location, i.code, json.dumps(i.details, sort_keys=True, separators=(",", ":"))))

        if issues:
            for issue in issues:
                events.append(_event_line("FAIL", issue.stage, issue.code, issue.location, issue.message, **issue.details))
            return "FAIL", issues, events

        return "PASS", [], events

    # ----------------------------
    # Internal storage mechanics
    # ----------------------------

    def _put_object(self, scope_root: Path, digest_hex: str, canonical_bytes: bytes) -> None:
        path = _objects_path(scope_root, digest_hex)
        if path.exists():
            return
        _atomic_write_bytes(path, canonical_bytes)

    def _get_object_json(self, scope_root: Path, digest_hex: str) -> Any:
        path = _objects_path(scope_root, digest_hex)
        if not path.exists():
            return None
        return _read_json(path)

    def _update_refs_by_id(self, scope_root: Path, new_sources: list[RefSource]) -> None:
        """
        Non-owning symbol table update (within a single scope):
        - For each (type,id), load record (if any)
        - Remove all existing sources with same stem (stem-scoped pruning within scope)
        - Add new sources
        - Sort deterministically and write canonical JSON
        - Emit multi-source collisions is left to promotion/host; we only persist truth.
        """
        # Group by (type,id) for minimal writes
        grouped: dict[tuple[str, str], list[RefSource]] = {}
        for s in new_sources:
            # We need the ref's type/id; store them encoded in location? No.
            # For minimal v1: caller passes sources grouped per ref type/id via this method.
            # stage_triplet builds sources from links, but we didn’t carry type/id in RefSource.
            # So: rebuild from location is impossible. Fix: accept sources grouped externally.
            raise RuntimeError(
                "Internal contract error: _update_refs_by_id requires ref_type/ref_id grouping. "
                "Call _update_refs_by_id_grouped()."
            )

    def _update_refs_by_id_grouped(self, scope_root: Path, grouped: dict[tuple[str, str], list[RefSource]]) -> None:
        for (ref_type, ref_id), sources_for_ref in grouped.items():
            path = _refs_by_id_path(scope_root, ref_type, ref_id)
            existing = {"type": ref_type, "id": ref_id, "sources": []}
            if path.exists():
                data = _read_json(path)
                if isinstance(data, dict):
                    existing = data

            existing_sources = existing.get("sources")
            if not isinstance(existing_sources, list):
                existing_sources = []

            # Stem-scoped pruning within scope
            stems_to_replace = {s.stem for s in sources_for_ref}
            pruned = [s for s in existing_sources if isinstance(s, dict) and s.get("stem") not in stems_to_replace]

            # Inject new
            injected = pruned + [
                {
                    "stem": s.stem,
                    "location": s.location,
                    "relationship": s.relationship,
                    "artifact_digest": s.artifact_digest,
                }
                for s in sources_for_ref
            ]

            # Deterministic sort: (stem, location, relationship, artifact_digest)
            def sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
                stem = str(item.get("stem") or "")
                loc = str(item.get("location") or "")
                rel = str(item.get("relationship") or "")
                dig = str(item.get("artifact_digest") or "")
                return (stem, loc, rel, dig)

            injected_sorted = sorted(injected, key=sort_key)

            record = {
                "lsi_version": LSI_VERSION,
                "type": ref_type,
                "id": ref_id,
                "sources": injected_sorted,
            }
            _atomic_write_json(path, record)

    def _lookup_ref_visibility(self, run_id: str, turn_id: str, stem: str, ref_type: str, ref_id: str) -> str | None:
        """
        Visibility layers (strict):
          1) Self: staging refs/by_id contains a source whose stem == current stem
          2) Staging: staging refs/by_id exists
          3) Committed: committed refs/by_id exists
        """
        # Self + staging
        staging_sources = self.read_refs_sources(scope=DIR_STAGING, ref_type=ref_type, ref_id=ref_id, run_id=run_id, turn_id=turn_id)
        if any(s.get("stem") == stem for s in staging_sources):
            return "Self"
        if staging_sources:
            return "Staging"

        committed_sources = self.read_refs_sources(scope=DIR_COMMITTED, ref_type=ref_type, ref_id=ref_id)
        if committed_sources:
            return "Committed"

        return None


# ----------------------------
# Patch: stage_triplet needs grouped ref update
# ----------------------------

def _event_line(level: str, stage: str, code: str, loc: str, message: str, **details: Any) -> str:
    # Minimal deterministic, single-line, pipe-guaranteed event format
    escaped_msg = str(message).replace("\r", r"\r").replace("\n", r"\n")

    def fmt(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (dict, list)):
            return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return str(v).replace("\r", r"\r").replace("\n", r"\n")

    detail_text = " ".join(f"{k}={fmt(details[k])}" for k in sorted(details.keys()))
    return f"[{level}] [STAGE:{stage}] [CODE:{code}] [LOC:{loc}] {escaped_msg} | {detail_text}"


# Monkey-patch the grouping behavior into stage_triplet cleanly without rewriting above block:
# (keeps the file minimal and readable; you can refactor later.)

def _stage_triplet_grouped_update(self: LocalSovereignIndex, *, run_id: str, turn_id: str, stem: str, body: dict[str, Any], links: dict[str, Any], manifest: dict[str, Any]) -> TripletDigests:
    stem = stem.replace("\\", "/").strip("/")

    scope_root = _scope_root(self.root, DIR_STAGING, run_id, turn_id)

    body_bytes = canonical_json_bytes(body)
    links_bytes = canonical_json_bytes(links)
    manifest_bytes = canonical_json_bytes(manifest)

    body_digest = structural_digest(body_bytes)
    links_digest = structural_digest(links_bytes)
    manifest_digest = structural_digest(manifest_bytes)

    self._put_object(scope_root, body_digest, body_bytes)
    self._put_object(scope_root, links_digest, links_bytes)
    self._put_object(scope_root, manifest_digest, manifest_bytes)

    dto_type = None
    if isinstance(body.get("dto_type"), str):
        dto_type = body["dto_type"].strip().lower()

    record = {
        "lsi_version": LSI_VERSION,
        "stem": stem,
        "dto_type": dto_type,
        "body_digest": body_digest,
        "links_digest": links_digest,
        "manifest_digest": manifest_digest,
        "updated_at_turn": turn_id,
    }
    _atomic_write_json(_triplets_path(scope_root, stem), record)

    # Build grouped refs
    grouped: dict[tuple[str, str], list[RefSource]] = {}
    for ref_type, ref_id, ptr, relationship in _iter_refs_from_links(links):
        grouped.setdefault((ref_type, ref_id), []).append(
            RefSource(
                stem=stem,
                location=ptr,
                relationship=relationship,
                artifact_digest=links_digest,
            )
        )

    self._update_refs_by_id_grouped(scope_root, grouped)

    return TripletDigests(
        dto_type=dto_type,
        body_digest=body_digest,
        links_digest=links_digest,
        manifest_digest=manifest_digest,
    )


# Replace the earlier stage_triplet with the grouped implementation
LocalSovereignIndex.stage_triplet = _stage_triplet_grouped_update  # type: ignore[attr-defined]