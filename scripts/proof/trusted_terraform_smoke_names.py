from __future__ import annotations

import hashlib
import re
from typing import Any

SMOKE_BUCKET_PREFIX = "orket-smoke-"
SMOKE_TABLE_PREFIX = "TerraformReviewsSmoke_"
SMOKE_OWNER_KEY = "OrketSmokeOwner"
SMOKE_LANE = "northstar-disposable-aws-smoke"

_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_TABLE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,255}$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def generate_smoke_suffix(seed: str) -> str:
    normalized = _require_seed(seed)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def generate_bucket_name(seed: str) -> str:
    return f"{SMOKE_BUCKET_PREFIX}{generate_smoke_suffix(seed)}"


def generate_table_name(seed: str) -> str:
    return f"{SMOKE_TABLE_PREFIX}{generate_smoke_suffix(seed)}"


def validate_smoke_bucket_name(name: str) -> None:
    value = str(name or "").strip()
    if contains_placeholder(value):
        raise ValueError(f"bucket_name_contains_placeholder:{value}")
    if not _BUCKET_RE.fullmatch(value):
        raise ValueError(f"invalid_s3_bucket_name:{value}")
    if ".." in value or ".-" in value or "-." in value:
        raise ValueError(f"invalid_s3_bucket_name:{value}")
    if _IP_ADDRESS_RE.fullmatch(value):
        raise ValueError(f"invalid_s3_bucket_name_ip_address:{value}")


def validate_smoke_table_name(name: str) -> None:
    value = str(name or "").strip()
    if contains_placeholder(value):
        raise ValueError(f"table_name_contains_placeholder:{value}")
    if not _TABLE_RE.fullmatch(value):
        raise ValueError(f"invalid_dynamodb_table_name:{value}")


def contains_placeholder(value: str) -> bool:
    text = str(value or "")
    return bool(_PLACEHOLDER_RE.search(text)) or "<unique-suffix>" in text or "<suffix>" in text


def smoke_owner_marker(seed: str) -> str:
    return f"{SMOKE_LANE}:{generate_smoke_suffix(seed)}"


def smoke_ownership_tags(seed: str) -> list[dict[str, str]]:
    marker = smoke_owner_marker(seed)
    return [
        {"Key": SMOKE_OWNER_KEY, "Value": marker},
        {"Key": "OrketLane", "Value": SMOKE_LANE},
    ]


def smoke_ownership_metadata(seed: str) -> dict[str, str]:
    return {"orket-smoke-owner": smoke_owner_marker(seed), "orket-lane": SMOKE_LANE}


def validate_operator_names(*, bucket: str, table_name: str) -> None:
    validate_smoke_bucket_name(bucket)
    validate_smoke_table_name(table_name)


def name_summary(*, seed: str, bucket: str, table_name: str) -> dict[str, Any]:
    return {
        "seed": str(seed or ""),
        "suffix": generate_smoke_suffix(seed),
        "bucket": bucket,
        "table_name": table_name,
        "smoke_owner_marker": smoke_owner_marker(seed),
    }


def _require_seed(seed: str) -> str:
    normalized = str(seed or "").strip()
    if not normalized:
        raise ValueError("smoke_seed_required")
    if contains_placeholder(normalized):
        raise ValueError("smoke_seed_contains_placeholder")
    return normalized
