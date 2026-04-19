from __future__ import annotations

import copy
from typing import Any

from scripts.proof.offline_trusted_run_verifier import CLAIM_ORDER


def without_diff_ledger(value: Any) -> dict[str, Any]:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def text(value: Any) -> str:
    return str(value or "").strip()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def forbidden_claim(claim: str, reasons: list[str]) -> dict[str, Any]:
    deduped = unique(reasons)
    return {
        "claim_tier": claim,
        "reason_codes": deduped,
        "missing_evidence": deduped,
        "blocking_check_ids": deduped,
    }


def all_claims_forbidden(reasons: list[str]) -> list[dict[str, Any]]:
    return [forbidden_claim(claim, reasons) for claim in CLAIM_ORDER]


def highest_allowed_claim(allowed: list[str]) -> str:
    ranked = [claim for claim in CLAIM_ORDER if claim in allowed]
    return ranked[-1] if ranked else ""
