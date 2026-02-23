# orket/kernel/v1/state/promotion.py
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from orket.kernel.v1.canonical import canonical_json_bytes, fs_token, structural_digest
from orket.kernel.v1.contracts import KernelIssue

# Keep these aligned with lsi.py (minimal v1)
LSI_VERSION = "lsi/v1"

DIR_INDEX = "index"
DIR_COMMITTED = "committed"
DIR_STAGING = "staging"
DIR_OBJECTS = "objects"
DIR_TRIPLETS = "triplets"
DIR_REFS = "refs"
DIR_BY_ID = "by_id"

E_PROMOTION_FAILED = "E_PROMOTION_FAILED"
E_PROMOTION_OUT_OF_ORDER = "E_PROMOTION_OUT_OF_ORDER"
E_PROMOTION_ALREADY_APPLIED = "E_PROMOTION_ALREADY_APPLIED"
E_TOMBSTONE_INVALID = "E_TOMBSTONE_INVALID"
E_TOMBSTONE_STEM_MISMATCH = "E_TOMBSTONE_STEM_MISMATCH"
I_REF_MULTISOURCE = "I_REF_MULTISOURCE"
I_NOOP_PROMOTION = "I_NOOP_PROMOTION"
RUN_LEDGER_FILE = "run_ledger.json"
TURN_ID_RE = re.compile(r"^turn-(\d{4})$")


@dataclass(frozen=True)
class PromotionResult:
    outcome: str  # "PASS" | "FAIL"
    promoted_stems: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    issues: list[KernelIssue] = field(default_factory=list)


@dataclass(frozen=True)
class RefSource:
    stem: str
    location: str
    relationship: str | None
    artifact_digest: str


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _event_line(level: str, stage: str, code: str, loc: str, message: str, **details: Any) -> str:
    # Single-line, pipe-delimited, deterministic ordering, newline safe.
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


def _root_index(root: str) -> Path:
    return Path(root) / DIR_INDEX


def _scope_root(root: str, scope: str, run_id: str | None = None, turn_id: str | None = None) -> Path:
    base = _root_index(root)
    if scope == DIR_COMMITTED:
        return base / DIR_COMMITTED
    if scope == DIR_STAGING:
        if not run_id or not turn_id:
            raise ValueError("staging scope requires run_id and turn_id")
        return base / DIR_STAGING / fs_token(run_id) / fs_token(turn_id)
    raise ValueError(f"unknown scope: {scope}")


def _parse_turn_index(turn_id: str) -> int:
    match = TURN_ID_RE.fullmatch(turn_id.strip())
    if not match:
        raise ValueError(f"invalid turn_id format: {turn_id}")
    return int(match.group(1))


def _ledger_path(committed_root: Path) -> Path:
    return committed_root / DIR_INDEX / RUN_LEDGER_FILE


def _load_last_promoted_turn_id(committed_root: Path) -> str:
    path = _ledger_path(committed_root)
    if not path.exists():
        return "turn-0000"
    try:
        data = _read_json(path)
    except Exception:
        return "turn-0000"
    if isinstance(data, dict):
        value = data.get("last_promoted_turn_id")
        if isinstance(value, str) and TURN_ID_RE.fullmatch(value):
            return value
    return "turn-0000"


def _save_last_promoted_turn_id(committed_root: Path, turn_id: str) -> None:
    _atomic_write_json(
        _ledger_path(committed_root),
        {
            "lsi_version": LSI_VERSION,
            "last_promoted_turn_id": turn_id,
        },
    )


def _triplets_dir(scope_root: Path) -> Path:
    return scope_root / DIR_TRIPLETS


def _objects_dir(scope_root: Path) -> Path:
    return scope_root / DIR_OBJECTS


def _refs_by_id_dir(scope_root: Path) -> Path:
    return scope_root / DIR_REFS / DIR_BY_ID


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
    Yield (ref_type, ref_id, pointer_to_ref_obj, relationship)
    pointer rooted at /links
    """
    for key in sorted(links.keys()):
        val = links[key]
        key_ptr = f"/links/{_pointer_token(key)}"

        if isinstance(val, list):
            for idx, item in enumerate(val):
                if not _is_ref_object(item):
                    continue
                ptr = f"{key_ptr}/{idx}"
                rel = item.get("relationship") if isinstance(item.get("relationship"), str) else None
                yield (item["type"], item["id"], ptr, rel)
        elif _is_ref_object(val):
            rel = val.get("relationship") if isinstance(val.get("relationship"), str) else None
            yield (val["type"], val["id"], key_ptr, rel)


def _links_object_from_staged_triplet(staging_root: Path, triplet_record: dict[str, Any]) -> dict[str, Any] | None:
    digest = triplet_record.get("links_digest")
    if not isinstance(digest, str) or not digest:
        return None
    obj_path = _objects_dir(staging_root) / digest[:2] / digest
    if not obj_path.exists():
        return None
    loaded = _read_json(obj_path)
    return loaded if isinstance(loaded, dict) else None


def _list_staged_stems(staging_root: Path) -> list[str]:
    td = _triplets_dir(staging_root)
    if not td.exists():
        return []
    stems: list[str] = []
    for p in td.rglob("*.json"):
        if p.name.endswith(".tombstone.json"):
            continue
        # stem is relative path without .json suffix, with forward slashes
        rel = p.relative_to(td).as_posix()
        if rel.endswith(".json"):
            stems.append(rel[: -len(".json")])
    return sorted(stems)


def _load_tombstone_stems(staging_root: Path, turn_id: str) -> tuple[set[str], list[KernelIssue], list[str]]:
    td = _triplets_dir(staging_root)
    stems: set[str] = set()
    issues: list[KernelIssue] = []
    events: list[str] = []
    if not td.exists():
        return stems, issues, events

    for p in sorted(td.rglob("*.tombstone.json"), key=lambda x: x.as_posix()):
        rel = p.relative_to(td).as_posix()
        stem_from_filename = rel[: -len(".tombstone.json")]
        loc_base = f"/index/staging/triplets/{_pointer_token(rel)}"
        try:
            payload = _read_json(p)
        except Exception as exc:  # noqa: BLE001
            issues.append(
                KernelIssue(
                    level="FAIL",
                    stage="promotion",
                    code=E_TOMBSTONE_INVALID,
                    location=loc_base,
                    message="Tombstone JSON parse failed.",
                    details={"error": str(exc)},
                )
            )
            events.append(_event_line("FAIL", "promotion", E_TOMBSTONE_INVALID, loc_base, "Tombstone JSON parse failed.", error=str(exc)))
            continue

        valid_shape = (
            isinstance(payload, dict)
            and payload.get("kind") == "tombstone"
            and isinstance(payload.get("stem"), str)
            and isinstance(payload.get("dto_type"), str)
            and isinstance(payload.get("id"), str)
            and isinstance(payload.get("deleted_by_turn_id"), str)
        )
        if not valid_shape:
            issues.append(
                KernelIssue(
                    level="FAIL",
                    stage="promotion",
                    code=E_TOMBSTONE_INVALID,
                    location=loc_base,
                    message="Tombstone payload is invalid.",
                    details={"required": ["kind", "stem", "dto_type", "id", "deleted_by_turn_id"]},
                )
            )
            events.append(
                _event_line(
                    "FAIL",
                    "promotion",
                    E_TOMBSTONE_INVALID,
                    loc_base,
                    "Tombstone payload is invalid.",
                    required=["kind", "stem", "dto_type", "id", "deleted_by_turn_id"],
                )
            )
            continue

        payload_stem = str(payload["stem"]).replace("\\", "/").strip("/")
        if payload_stem != stem_from_filename:
            issues.append(
                KernelIssue(
                    level="FAIL",
                    stage="promotion",
                    code=E_TOMBSTONE_STEM_MISMATCH,
                    location=f"{loc_base}/stem",
                    message="Tombstone stem does not match filename-derived stem.",
                    details={"expected": stem_from_filename, "actual": payload_stem},
                )
            )
            events.append(
                _event_line(
                    "FAIL",
                    "promotion",
                    E_TOMBSTONE_STEM_MISMATCH,
                    f"{loc_base}/stem",
                    "Tombstone stem does not match filename-derived stem.",
                    expected=stem_from_filename,
                    actual=payload_stem,
                )
            )
            continue

        if payload.get("deleted_by_turn_id") != turn_id:
            issues.append(
                KernelIssue(
                    level="FAIL",
                    stage="promotion",
                    code=E_TOMBSTONE_INVALID,
                    location=f"{loc_base}/deleted_by_turn_id",
                    message="Tombstone deleted_by_turn_id must match promotion turn.",
                    details={"expected": turn_id, "actual": payload.get("deleted_by_turn_id")},
                )
            )
            events.append(
                _event_line(
                    "FAIL",
                    "promotion",
                    E_TOMBSTONE_INVALID,
                    f"{loc_base}/deleted_by_turn_id",
                    "Tombstone deleted_by_turn_id must match promotion turn.",
                    expected=turn_id,
                    actual=payload.get("deleted_by_turn_id"),
                )
            )
            continue

        stems.add(stem_from_filename)

    return stems, issues, events


def _remove_sources_for_stem(record: dict[str, Any], stem: str) -> dict[str, Any]:
    sources = record.get("sources")
    if not isinstance(sources, list):
        sources = []
    pruned = [s for s in sources if isinstance(s, dict) and s.get("stem") != stem]
    record["sources"] = pruned
    return record


def _inject_sources(record: dict[str, Any], new_sources: list[RefSource]) -> dict[str, Any]:
    sources = record.get("sources")
    if not isinstance(sources, list):
        sources = []
    sources.extend(
        {
            "stem": s.stem,
            "location": s.location,
            "relationship": s.relationship,
            "artifact_digest": s.artifact_digest,
        }
        for s in new_sources
    )

    def sort_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(item.get("stem") or ""),
            str(item.get("location") or ""),
            str(item.get("relationship") or ""),
            str(item.get("artifact_digest") or ""),
        )

    record["sources"] = sorted([s for s in sources if isinstance(s, dict)], key=sort_key)
    return record


def _refs_record_path(scope_root: Path, ref_type: str, ref_id: str) -> Path:
    return _refs_by_id_dir(scope_root) / fs_token(ref_type) / f"{fs_token(ref_id)}.json"


def promote_turn(*, root: str, run_id: str, turn_id: str) -> PromotionResult:
    """
    Spec-002 Promotion (Minimal v1):
      - Promotion is "atomic" by directory swap:
          committed -> committed.__bak
          committed.__new -> committed
      - Copies committed into committed.__new (small tests; acceptable for v1)
      - Copies staged objects into committed.__new objects store
      - Copies staged triplet records into committed.__new triplets/
      - Enforces stem-scoped pruning across ALL committed refs records:
          remove all sources where source.stem == promoted_stem
      - Injects new sources derived from promoted stems' staged /links
      - Emits I_REF_MULTISOURCE events for any {type,id} with >1 sources after promotion
    """
    events: list[str] = []
    issues: list[KernelIssue] = []

    committed_root = _scope_root(root, DIR_COMMITTED)
    base = _root_index(root)
    staging_root = _scope_root(root, DIR_STAGING, run_id, turn_id)

    # Sequential ledger preflight.
    try:
        requested_turn_index = _parse_turn_index(turn_id)
        last_promoted_turn_id = _load_last_promoted_turn_id(committed_root)
        last_promoted_turn_index = _parse_turn_index(last_promoted_turn_id)
    except Exception as exc:  # noqa: BLE001
        issues.append(
            KernelIssue(
                level="FAIL",
                stage="promotion",
                code=E_PROMOTION_FAILED,
                location="/index/committed/index/run_ledger.json",
                message="Failed to parse promotion ledger or turn id.",
                details={"error": str(exc), "turn_id": turn_id},
            )
        )
        events.append(
            _event_line(
                "FAIL",
                "promotion",
                E_PROMOTION_FAILED,
                "/index/committed/index/run_ledger.json",
                "Failed to parse promotion ledger or turn id.",
                error=str(exc),
                turn_id=turn_id,
            )
        )
        return PromotionResult(outcome="FAIL", events=events, issues=issues)

    if requested_turn_index <= last_promoted_turn_index:
        issues.append(
            KernelIssue(
                level="FAIL",
                stage="promotion",
                code=E_PROMOTION_ALREADY_APPLIED,
                location="/index/committed/index/run_ledger.json",
                message="Promotion turn already applied or older than ledger state.",
                details={"turn_id": turn_id, "last_promoted_turn_id": last_promoted_turn_id},
            )
        )
        events.append(
            _event_line(
                "FAIL",
                "promotion",
                E_PROMOTION_ALREADY_APPLIED,
                "/index/committed/index/run_ledger.json",
                "Promotion turn already applied or stale.",
                turn_id=turn_id,
                last_promoted_turn_id=last_promoted_turn_id,
            )
        )
        return PromotionResult(outcome="FAIL", events=events, issues=issues)

    if requested_turn_index != (last_promoted_turn_index + 1):
        issues.append(
            KernelIssue(
                level="FAIL",
                stage="promotion",
                code=E_PROMOTION_OUT_OF_ORDER,
                location="/index/committed/index/run_ledger.json",
                message="Promotion turn is out of sequence.",
                details={"turn_id": turn_id, "last_promoted_turn_id": last_promoted_turn_id},
            )
        )
        events.append(
            _event_line(
                "FAIL",
                "promotion",
                E_PROMOTION_OUT_OF_ORDER,
                "/index/committed/index/run_ledger.json",
                "Promotion turn is out of sequence.",
                turn_id=turn_id,
                last_promoted_turn_id=last_promoted_turn_id,
            )
        )
        return PromotionResult(outcome="FAIL", events=events, issues=issues)

    promoted_stems = _list_staged_stems(staging_root) if staging_root.exists() else []
    tombstoned_stems: set[str] = set()
    if staging_root.exists():
        tombstoned_stems, tombstone_issues, tombstone_events = _load_tombstone_stems(staging_root, turn_id)
        if tombstone_issues:
            return PromotionResult(outcome="FAIL", promoted_stems=[], events=tombstone_events, issues=tombstone_issues)
        promoted_stems = sorted(set(promoted_stems) | tombstoned_stems)
    deletion_only = not staging_root.exists()
    if deletion_only:
        committed_triplets = _triplets_dir(committed_root)
        if committed_triplets.exists():
            promoted_stems = sorted(
                rel[: -len(".json")]
                for rel in (
                    str(p.relative_to(committed_triplets)).replace("\\", "/")
                    for p in committed_triplets.rglob("*.json")
                )
                if rel.endswith(".json")
            )

    new_root = base / f"{DIR_COMMITTED}.__new"
    bak_root = base / f"{DIR_COMMITTED}.__bak"

    try:
        # Ensure clean temp dirs
        if new_root.exists():
            shutil.rmtree(new_root)
        if bak_root.exists():
            shutil.rmtree(bak_root)

        # Seed new_root from current committed (if any)
        if committed_root.exists():
            shutil.copytree(committed_root, new_root)
        else:
            new_root.mkdir(parents=True, exist_ok=True)

        # 1) Copy staged objects (content-addressed) into new_root
        if staging_root.exists():
            staged_objects = _objects_dir(staging_root)
            if staged_objects.exists():
                for obj_file in staged_objects.rglob("*"):
                    if obj_file.is_dir():
                        continue
                    rel = obj_file.relative_to(staged_objects)
                    dest = _objects_dir(new_root) / rel
                    if dest.exists():
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(obj_file, dest)

        # 2) Copy staged triplet records into new_root (skip for deletion-only)
        if staging_root.exists():
            staged_triplets = _triplets_dir(staging_root)
            for stem in promoted_stems:
                src = (staged_triplets / Path(stem)).with_suffix(".json")
                dst = (_triplets_dir(new_root) / Path(stem)).with_suffix(".json")
                dst.parent.mkdir(parents=True, exist_ok=True)
                if stem in tombstoned_stems:
                    continue
                if src.exists():
                    shutil.copy2(src, dst)

        # 3) Stem-scoped pruning across ALL refs/by_id records in new_root
        refs_dir = _refs_by_id_dir(new_root)
        if refs_dir.exists():
            ref_files = sorted([p for p in refs_dir.rglob("*.json") if p.is_file()], key=lambda p: p.as_posix())
            for ref_file in ref_files:
                rec = _read_json(ref_file)
                if not isinstance(rec, dict):
                    continue
                for stem in promoted_stems:
                    rec = _remove_sources_for_stem(rec, stem)
                # Keep stable header fields if missing
                if "lsi_version" not in rec:
                    rec["lsi_version"] = LSI_VERSION
                _atomic_write_json(ref_file, rec)

        # Remove promoted stems' triplet records for deletion-only promotions.
        if deletion_only or tombstoned_stems:
            to_remove = set(promoted_stems) if deletion_only else set(tombstoned_stems)
            for stem in sorted(to_remove):
                dst = (_triplets_dir(new_root) / Path(stem)).with_suffix(".json")
                if dst.exists():
                    dst.unlink()

        # 4) Inject new sources derived from staged promoted stems
        # Group new sources by (type,id)
        grouped: dict[tuple[str, str], list[RefSource]] = {}
        staged_triplets_dir = _triplets_dir(staging_root)

        if staging_root.exists():
            for stem in promoted_stems:
                if stem in tombstoned_stems:
                    continue
                triplet_path = (staged_triplets_dir / Path(stem)).with_suffix(".json")
                if not triplet_path.exists():
                    continue
                trec = _read_json(triplet_path)
                if not isinstance(trec, dict):
                    continue
                links = _links_object_from_staged_triplet(staging_root, trec)
                if not isinstance(links, dict):
                    continue

                links_digest = trec.get("links_digest")
                if not isinstance(links_digest, str) or not links_digest:
                    continue

                for ref_type, ref_id, ptr, rel in _iter_refs_from_links(links):
                    grouped.setdefault((ref_type, ref_id), []).append(
                        RefSource(
                            stem=stem,
                            location=ptr,
                            relationship=rel,
                            artifact_digest=links_digest,
                        )
                    )

        # Apply grouped injections
        for (ref_type, ref_id), sources in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            path = _refs_record_path(new_root, ref_type, ref_id)
            path.parent.mkdir(parents=True, exist_ok=True)

            record: dict[str, Any] = {"lsi_version": LSI_VERSION, "type": ref_type, "id": ref_id, "sources": []}
            if path.exists():
                loaded = _read_json(path)
                if isinstance(loaded, dict):
                    record = loaded
                    if "lsi_version" not in record:
                        record["lsi_version"] = LSI_VERSION
                    if record.get("type") is None:
                        record["type"] = ref_type
                    if record.get("id") is None:
                        record["id"] = ref_id

            record = _inject_sources(record, sources)
            _atomic_write_json(path, record)

            # Collision observation
            sources_list = record.get("sources")
            if isinstance(sources_list, list) and len(sources_list) > 1:
                stems = sorted({str(s.get("stem") or "") for s in sources_list if isinstance(s, dict)})
                loc = f"/index/refs/by_id/{_pointer_token(ref_type)}/{_pointer_token(ref_id)}"
                events.append(_event_line("INFO", "promotion", I_REF_MULTISOURCE, loc, "Multiple stems reference the same {type,id}.", type=ref_type, id=ref_id, stems=stems))

        # 5) Directory swap to make promotion atomic
        if committed_root.exists():
            os.replace(committed_root, bak_root)
        os.replace(new_root, committed_root)
        _save_last_promoted_turn_id(committed_root, turn_id)
        if bak_root.exists():
            shutil.rmtree(bak_root)

        # Optional: remove the staging turn directory after successful promotion
        # (You may choose to retain evidence; minimal v1 purges staging on success.)
        if staging_root.exists():
            shutil.rmtree(staging_root)

        if not promoted_stems:
            events.append(
                _event_line(
                    "INFO",
                    "promotion",
                    I_NOOP_PROMOTION,
                    "/index/staging",
                    "No staged stems to promote.",
                    run_id=run_id,
                    turn_id=turn_id,
                )
            )
        events.append(_event_line("INFO", "promotion", "I_PROMOTION_PASS", "/index/committed", "Promotion completed.", run_id=run_id, turn_id=turn_id, stems=promoted_stems))
        return PromotionResult(outcome="PASS", promoted_stems=promoted_stems, events=events, issues=[])

    except Exception as exc:  # noqa: BLE001
        # Attempt best-effort cleanup and fail closed.
        msg = str(exc)
        issues.append(
            KernelIssue(
                level="FAIL",
                stage="promotion",
                code=E_PROMOTION_FAILED,
                location="/index/committed",
                message="Promotion failed; committed state not guaranteed updated.",
                details={"error": msg, "run_id": run_id, "turn_id": turn_id},
            )
        )
        events.append(_event_line("FAIL", "promotion", E_PROMOTION_FAILED, "/index/committed", "Promotion failed.", error=msg, run_id=run_id, turn_id=turn_id))

        # Cleanup new_root if it exists; do NOT delete bak_root automatically.
        if new_root.exists():
            try:
                shutil.rmtree(new_root)
            except Exception:
                pass

        return PromotionResult(outcome="FAIL", promoted_stems=[], events=events, issues=issues)
