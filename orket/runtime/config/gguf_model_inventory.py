from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_LLAMA_CPP_GGUF_MODEL_ROOT = Path("D:/models/GGUF")
DIGEST_STATUSES = {"missing", "pending", "computed", "failed", "skipped_by_policy"}


@dataclass(frozen=True)
class GGUFModelInventoryRecord:
    alias: str
    path: str
    size_bytes: int
    digest_status: str
    sha256: str = ""
    error: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GGUFModelInventoryResult:
    model_root: str
    status: str
    records: tuple[GGUFModelInventoryRecord, ...]
    error: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["records"] = [record.to_payload() for record in self.records]
        return payload


def normalize_digest_status(value: Any, *, default: str = "pending") -> str:
    token = str(value or "").strip().lower()
    if token in {"skip", "skipped", "skip_hash", "skipped_by_policy"}:
        token = "skipped_by_policy"
    if token in {"compute", "computed"}:
        token = "computed"
    if token in DIGEST_STATUSES:
        return token
    fallback = str(default or "").strip().lower()
    return fallback if fallback in DIGEST_STATUSES else "pending"


def resolve_gguf_model_root(
    raw: str | Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> Path:
    if raw is not None and str(raw).strip():
        return Path(str(raw).strip())
    env = environment if isinstance(environment, Mapping) else os.environ
    for key in ("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", "ORKET_LLAMA_CPP_MODEL_ROOT", "ORKET_GGUF_MODEL_ROOT"):
        token = str(env.get(key) or "").strip()
        if token:
            return Path(token)
    return DEFAULT_LLAMA_CPP_GGUF_MODEL_ROOT


def alias_from_gguf_path(path: Path | str) -> str:
    stem = Path(path).stem.strip()
    return stem.lower()


def is_gguf_path_inside_root(*, root: Path | str, candidate: Path | str) -> bool:
    try:
        root_path = Path(root).resolve()
        candidate_path = Path(candidate).resolve()
    except OSError:
        return False
    return candidate_path.is_relative_to(root_path)


def _record_for_file(
    *,
    root_path: Path,
    path: Path,
    digest_policy: str,
    digest_status_by_alias: Mapping[str, str],
    sha256_by_alias: Mapping[str, str],
) -> GGUFModelInventoryRecord | None:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.suffix.lower() != ".gguf":
        return None
    if not resolved.is_relative_to(root_path):
        return None
    alias = alias_from_gguf_path(resolved)
    digest_status = normalize_digest_status(digest_status_by_alias.get(alias), default=digest_policy)
    sha256 = str(sha256_by_alias.get(alias) or "").strip()
    if digest_status == "computed" and not sha256:
        digest_status = "failed"
    return GGUFModelInventoryRecord(
        alias=alias,
        path=str(resolved),
        size_bytes=int(resolved.stat().st_size),
        digest_status=digest_status,
        sha256=sha256,
    )


def inventory_gguf_models(
    *,
    model_root: str | Path | None = None,
    digest_policy: str | None = None,
    expected_aliases: tuple[str, ...] | list[str] = (),
    digest_status_by_alias: Mapping[str, str] | None = None,
    sha256_by_alias: Mapping[str, str] | None = None,
    environment: Mapping[str, str] | None = None,
) -> GGUFModelInventoryResult:
    root = resolve_gguf_model_root(model_root, environment=environment)
    try:
        root_path = root.resolve()
    except OSError as exc:
        return GGUFModelInventoryResult(model_root=str(root), status="BLOCKED", records=(), error=str(exc))
    if not root_path.exists() or not root_path.is_dir():
        return GGUFModelInventoryResult(
            model_root=str(root_path),
            status="BLOCKED",
            records=(),
            error="model_root_missing",
        )

    policy = normalize_digest_status(
        digest_policy
        or (environment if isinstance(environment, Mapping) else os.environ).get("ORKET_LLAMA_CPP_GGUF_DIGEST_POLICY")
        or "pending"
    )
    digest_status_map = digest_status_by_alias or {}
    sha256_map = sha256_by_alias or {}
    records: list[GGUFModelInventoryRecord] = []
    for path in sorted(root_path.rglob("*.gguf")):
        record = _record_for_file(
            root_path=root_path,
            path=path,
            digest_policy=policy,
            digest_status_by_alias=digest_status_map,
            sha256_by_alias=sha256_map,
        )
        if record is not None:
            records.append(record)

    aliases_seen = {record.alias for record in records}
    for alias in sorted({str(value).strip().lower() for value in expected_aliases if str(value).strip()}):
        if alias not in aliases_seen:
            records.append(
                GGUFModelInventoryRecord(
                    alias=alias,
                    path="",
                    size_bytes=0,
                    digest_status="missing",
                    error="expected_alias_missing",
                )
            )

    records = sorted(records, key=lambda record: (record.alias, record.path))
    has_present_model = any(record.path and record.digest_status != "missing" for record in records)
    return GGUFModelInventoryResult(
        model_root=str(root_path),
        status="OK" if has_present_model else "BLOCKED",
        records=tuple(records),
        error="" if has_present_model else "empty_inventory",
    )

