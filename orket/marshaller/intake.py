from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError

from .contracts import PatchProposal
from .rejection_codes import (
    BINARY_DELTA_DENIED,
    FORBIDDEN_PATH,
    PATCH_TOO_LARGE,
    RENAME_CAP_EXCEEDED,
    SCHEMA_INVALID,
    SECRETS_DETECTED,
)

_MAX_PATCH_BYTES_DEFAULT = 1_000_000
_RENAME_CAP_DEFAULT = 50
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
)


@dataclass(frozen=True)
class IntakeValidationResult:
    ok: bool
    rejection_codes: tuple[str, ...]
    primary_rejection_code: str | None
    errors: tuple[str, ...]
    proposal: PatchProposal | None = None


def validate_patch_proposal_payload(payload: Mapping[str, Any]) -> IntakeValidationResult:
    """Validate proposal schema and return deterministic errors/rejection code."""

    try:
        proposal = PatchProposal.model_validate(payload)
    except ValidationError as exc:
        return _failure((SCHEMA_INVALID,), _validation_errors(exc))
    return _success(proposal)


def evaluate_patch_proposal(
    payload: Mapping[str, Any],
    *,
    allowed_paths: Sequence[str] = (),
    max_patch_bytes: int = _MAX_PATCH_BYTES_DEFAULT,
    allow_binary_deltas: bool = False,
    rename_cap: int = _RENAME_CAP_DEFAULT,
    refactor_mode: bool = False,
) -> IntakeValidationResult:
    """Run Marshaller v0 Stage 0/1 intake checks in deterministic order."""

    parsed = validate_patch_proposal_payload(payload)
    if not parsed.ok or parsed.proposal is None:
        return parsed

    proposal = parsed.proposal
    rejection_codes: list[str] = []
    if _has_forbidden_paths(proposal.touched_paths, allowed_paths):
        rejection_codes.append(FORBIDDEN_PATH)
    if len(proposal.patch.encode("utf-8")) > max_patch_bytes:
        rejection_codes.append(PATCH_TOO_LARGE)
    if _contains_secret(proposal.patch):
        rejection_codes.append(SECRETS_DETECTED)
    if not allow_binary_deltas and _contains_binary_delta(proposal.patch):
        rejection_codes.append(BINARY_DELTA_DENIED)
    if not refactor_mode and _rename_count(proposal.patch) > rename_cap:
        rejection_codes.append(RENAME_CAP_EXCEEDED)

    if rejection_codes:
        return _failure(tuple(rejection_codes))
    return _success(proposal)


def _validation_errors(exc: ValidationError) -> tuple[str, ...]:
    rows: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        msg = str(err.get("msg", "validation error")).strip()
        rows.append(f"{loc}: {msg}")
    return tuple(sorted(rows))


def _success(proposal: PatchProposal) -> IntakeValidationResult:
    return IntakeValidationResult(
        ok=True,
        rejection_codes=(),
        primary_rejection_code=None,
        errors=(),
        proposal=proposal,
    )


def _failure(codes: tuple[str, ...], errors: tuple[str, ...] = ()) -> IntakeValidationResult:
    return IntakeValidationResult(
        ok=False,
        rejection_codes=codes,
        primary_rejection_code=codes[0] if codes else None,
        errors=errors,
        proposal=None,
    )


def _contains_secret(patch: str) -> bool:
    return any(pattern.search(patch) for pattern in _SECRET_PATTERNS)


def _contains_binary_delta(patch: str) -> bool:
    return "GIT binary patch" in patch or "Binary files " in patch


def _rename_count(patch: str) -> int:
    return sum(1 for line in patch.splitlines() if line.startswith("rename from "))


def _has_forbidden_paths(touched_paths: Sequence[str], allowed_paths: Sequence[str]) -> bool:
    allowed = [_normalize_allowlist_path(item) for item in allowed_paths if _normalize_allowlist_path(item)]
    for raw_path in touched_paths:
        path = _normalize_path(raw_path)
        if not path:
            return True
        if _is_absolute_or_drive(path):
            return True
        if _contains_traversal(path):
            return True
        if allowed and not _is_under_allowlist(path, allowed):
            return True
    return False


def _normalize_path(value: str) -> str:
    candidate = str(value).strip().replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    return candidate


def _normalize_allowlist_path(value: str) -> str:
    candidate = _normalize_path(value)
    return candidate.rstrip("/")


def _is_absolute_or_drive(path: str) -> bool:
    return path.startswith("/") or bool(_DRIVE_PREFIX.match(path))


def _contains_traversal(path: str) -> bool:
    return ".." in PurePosixPath(path).parts


def _is_under_allowlist(path: str, allowed: Sequence[str]) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in allowed)
