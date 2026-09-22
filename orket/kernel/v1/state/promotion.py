"""Application-owned local promotion; directory publication is not crash-atomic."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage import kernel_state_store as store
from orket.application.services.kernel_invocation_inputs import capture_kernel_invocation_root
from orket.core.contracts.kernel_triplet import pointer_token as _pointer_token
from orket.kernel.v1.contracts import KernelIssue

from . import promotion_effects as effects
from .layout import (
    DIR_COMMITTED,
    DIR_INDEX,
    LSI_VERSION,
    triplets_path,
)
from .layout import (
    event_line as _event_line,
)
from .layout import (
    scope_root as _scope_root,
)
from .layout import (
    triplets_dir as _triplets_dir,
)
from .layout import (
    write_json as _atomic_write_json,
)

E_PROMOTION_FAILED = "E_PROMOTION_FAILED"
E_PROMOTION_OUT_OF_ORDER = "E_PROMOTION_OUT_OF_ORDER"
E_PROMOTION_ALREADY_APPLIED = "E_PROMOTION_ALREADY_APPLIED"
E_TOMBSTONE_INVALID = "E_TOMBSTONE_INVALID"
E_TOMBSTONE_STEM_MISMATCH = "E_TOMBSTONE_STEM_MISMATCH"
I_NOOP_PROMOTION = "I_NOOP_PROMOTION"
RUN_LEDGER_FILE = "run_ledger.json"
TURN_ID_RE = re.compile(r"^turn-(\d{4})$")
REPAIR_ACKNOWLEDGEMENT = "I_ACKNOWLEDGE_DATA_GAP"


@dataclass(frozen=True)
class PromotionResult:
    outcome: str  # "PASS" | "FAIL"
    promoted_stems: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    issues: list[KernelIssue] = field(default_factory=list)


def _parse_turn_index(turn_id: str) -> int:
    match = TURN_ID_RE.fullmatch(turn_id)
    if not match:
        raise ValueError(f"invalid turn_id format: {turn_id}")
    return int(match.group(1))


def _ledger_path(committed_root: Path) -> Path:
    return committed_root / DIR_INDEX / RUN_LEDGER_FILE


def _load_last_promoted_turn_id(committed_root: Path) -> str:
    path = _ledger_path(committed_root)
    if not store.exists(path):
        return "turn-0000"
    try:
        data = store.read_json(path)
    except OSError as exc:
        raise ValueError(f"ledger I/O error: {exc}") from exc
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"ledger corrupt: {exc}") from exc
    if isinstance(data, dict):
        value = data.get("last_promoted_turn_id")
        if isinstance(value, str) and TURN_ID_RE.fullmatch(value):
            return value
    raise ValueError("ledger corrupt: valid last_promoted_turn_id is required")


def _save_last_promoted_turn_id(committed_root: Path, turn_id: str) -> None:
    _atomic_write_json(
        _ledger_path(committed_root),
        {
            "lsi_version": LSI_VERSION,
            "last_promoted_turn_id": turn_id,
        },
    )


def repair_run_ledger(root: str, *, force_turn_id: str, acknowledge: str) -> None:
    """
    Force the promotion ledger past a missing or corrupted turn after an explicit
    operator acknowledgment of the resulting continuity gap.
    """
    require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
    if acknowledge != REPAIR_ACKNOWLEDGEMENT:
        raise ValueError("repair_run_ledger requires explicit data-gap acknowledgment")
    _parse_turn_index(force_turn_id)
    committed_root = _scope_root(capture_kernel_invocation_root(root).root, DIR_COMMITTED)
    _save_last_promoted_turn_id(committed_root, force_turn_id)


def _list_staged_stems(staging_root: Path) -> list[str]:
    td = _triplets_dir(staging_root)
    if not store.exists(td):
        return []
    stems: list[str] = []
    for p in store.paths(td, "*.json"):
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
    if not store.exists(td):
        return stems, issues, events

    for p in sorted(store.paths(td, "*.tombstone.json"), key=lambda x: x.as_posix()):
        rel = p.relative_to(td).as_posix()
        stem_from_filename = rel[: -len(".tombstone.json")]
        loc_base = f"/index/staging/triplets/{_pointer_token(rel)}"
        try:
            payload = store.read_json(p)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
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
            events.append(
                _event_line(
                    "FAIL", "promotion", E_TOMBSTONE_INVALID, loc_base, "Tombstone JSON parse failed.", error=str(exc)
                )
            )
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

def _refusal(code: str, location: str, message: str, **details) -> PromotionResult:
    issue = KernelIssue(stage="promotion", code=code, location=location, message=message, details=details)
    return PromotionResult(outcome="FAIL", issues=[issue], events=[
        _event_line("FAIL", "promotion", code, location, message, **details)])


def _check_order(paths: effects.PromotionPaths, turn_id: str) -> PromotionResult | None:
    location = "/index/committed/index/run_ledger.json"
    try:
        requested = _parse_turn_index(turn_id)
        last = _load_last_promoted_turn_id(paths.committed)
        previous = _parse_turn_index(last)
    except (ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
        return _refusal(E_PROMOTION_FAILED, location, "Failed to parse promotion ledger or turn id.", error=str(exc), turn_id=turn_id)
    details = dict(turn_id=turn_id, last_promoted_turn_id=last)
    if requested <= previous:
        return _refusal(E_PROMOTION_ALREADY_APPLIED, location, "Promotion turn already applied or older than ledger state.", **details)
    if requested != previous + 1:
        return _refusal(E_PROMOTION_OUT_OF_ORDER, location, "Promotion turn is out of sequence.", **details)
    return None


def _failed_publication(paths: effects.PromotionPaths, run_id: str, turn_id: str, error: Exception,
                        candidate_owned: bool) -> PromotionResult:
    result = _refusal(E_PROMOTION_FAILED, "/index/committed",
        "Promotion failed; committed state not guaranteed updated.", error=str(error), run_id=run_id, turn_id=turn_id)
    if candidate_owned:
        try:
            if store.exists(paths.candidate):
                store.remove_tree(paths.candidate)
        except OSError as cleanup_error:
            cleanup = _refusal("E_PROMOTION_CLEANUP_FAILED", "/index/committed.__new",
                "Promotion candidate cleanup failed; inspect retained state.", error=str(cleanup_error))
            result.issues.extend(cleanup.issues)
            result.events.extend(cleanup.events)
    return result


def promote_turn(*, root: str, run_id: str, turn_id: str) -> PromotionResult:
    """Validate order, classify explicit work, and retain publication failures."""
    require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
    captured_root = capture_kernel_invocation_root(root).root
    paths = effects.PromotionPaths.capture(captured_root, run_id, turn_id)
    refused = _check_order(paths, turn_id)
    if refused is not None:
        return refused
    candidate_owned = False
    try:
        stems = _list_staged_stems(paths.staging)
        tombstones, issues, events = _load_tombstone_stems(paths.staging, turn_id)
        if issues:
            return PromotionResult(outcome="FAIL", issues=issues, events=events)
        stems = sorted(set(stems) | tombstones)
        for stem in stems:
            triplets_path(paths.staging, stem)
        effects.require_unused_candidate(paths)
        if not stems:
            _save_last_promoted_turn_id(paths.committed, turn_id)
            events.append(_event_line("INFO", "promotion", I_NOOP_PROMOTION, "/index/staging",
                "No staged stems to promote.", run_id=run_id, turn_id=turn_id))
        else:
            grouped = effects.collect_sources(paths, stems, tombstones)
            candidate_owned = True
            effects.seed_candidate(paths)
            effects.copy_staged_objects(paths)
            effects.copy_staged_triplets(paths, stems, tombstones)
            effects.prune_sources(paths, stems, tombstones)
            events.extend(effects.inject_sources(paths.candidate, grouped))
            effects.replace_candidate(paths)
            _save_last_promoted_turn_id(paths.committed, turn_id)
            effects.cleanup_success(paths)
        events.append(_event_line("INFO", "promotion", "I_PROMOTION_PASS", "/index/committed",
            "Promotion completed.", run_id=run_id, turn_id=turn_id, stems=stems))
        return PromotionResult(outcome="PASS", promoted_stems=stems, events=events)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, shutil.Error) as exc:
        return _failed_publication(paths, run_id, turn_id, exc, candidate_owned)
