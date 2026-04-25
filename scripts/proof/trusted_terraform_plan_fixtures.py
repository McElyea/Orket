from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.terraform_review.deterministic import analyze_plan, digest_plan_bytes, parse_plan_json

SAFE_FIXTURE_KIND = "safe_create_update"
RISKY_FIXTURE_KIND = "risky_delete_replace"
FIXTURE_KIND_ALIASES = {
    "safe": SAFE_FIXTURE_KIND,
    SAFE_FIXTURE_KIND: SAFE_FIXTURE_KIND,
    "risky": RISKY_FIXTURE_KIND,
    RISKY_FIXTURE_KIND: RISKY_FIXTURE_KIND,
}
FORBIDDEN_OPERATIONS = ["destroy", "replace"]


@dataclass(frozen=True, slots=True)
class GeneratedTerraformPlanFixture:
    plan_payload: dict[str, Any]
    metadata: dict[str, Any]


def normalize_fixture_kind(kind: str) -> str:
    normalized = str(kind or "").strip()
    try:
        return FIXTURE_KIND_ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported_fixture_kind:{kind}") from exc


def build_plan_fixture(*, fixture_kind: str, fixture_seed: str) -> GeneratedTerraformPlanFixture:
    kind = normalize_fixture_kind(fixture_kind)
    seed = _require_seed(fixture_seed)
    rng = random.Random(seed)
    changes = _safe_changes(rng, seed) if kind == SAFE_FIXTURE_KIND else _risky_changes(rng, seed)
    plan_payload = {"format_version": "1.1", "resource_changes": changes}
    plan_bytes = render_plan_bytes(plan_payload)
    analysis = analyze_plan(plan_payload=plan_payload, forbidden_operations=FORBIDDEN_OPERATIONS)
    expected_verdict = "risky_for_v1_policy" if analysis.forbidden_operation_hits else "safe_for_v1_policy"
    metadata = {
        "schema_version": "trusted_terraform_plan_fixture_metadata.v1",
        "fixture_seed": seed,
        "fixture_kind": kind,
        "expected_verdict": expected_verdict,
        "resource_names": [str(item["address"]) for item in changes],
        "action_mix": _action_mix(changes),
        "plan_hash": digest_plan_bytes(plan_bytes),
        "observed_path": "primary",
        "observed_result": "success",
    }
    return GeneratedTerraformPlanFixture(plan_payload=plan_payload, metadata=metadata)


def render_plan_bytes(plan_payload: dict[str, Any]) -> bytes:
    return (json.dumps(plan_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def write_plan_fixture(plan_path: Path, plan_payload: dict[str, Any]) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(render_plan_bytes(plan_payload))


def validate_plan_fixture_payload(*, plan_bytes: bytes, expected_verdict: str) -> dict[str, Any]:
    payload, parse_error = parse_plan_json(plan_bytes)
    if payload is None:
        return _validation_report("blocked", "failure", [parse_error], "", {}, [])
    analysis = analyze_plan(plan_payload=payload, forbidden_operations=FORBIDDEN_OPERATIONS)
    failures = _analysis_failures(analysis.to_dict())
    actual_verdict = "risky_for_v1_policy" if analysis.forbidden_operation_hits else "safe_for_v1_policy"
    if str(expected_verdict or "").strip() and actual_verdict != str(expected_verdict).strip():
        failures.append("expected_verdict_mismatch")
    return _validation_report(
        "primary" if not failures else "blocked",
        "success" if not failures else "failure",
        failures,
        actual_verdict,
        analysis.to_dict(),
        _unsupported_actions(payload),
    )


def plan_digest_from_path(path: Path) -> str:
    return digest_plan_bytes(path.read_bytes())


def _safe_changes(rng: random.Random, seed: str) -> list[dict[str, Any]]:
    actions = [["create"], ["update"], ["no-op"]]
    rng.shuffle(actions)
    selected = actions[: rng.randint(2, 3)]
    return [_change(seed=seed, index=index, actions=actions_value, rng=rng) for index, actions_value in enumerate(selected)]


def _risky_changes(rng: random.Random, seed: str) -> list[dict[str, Any]]:
    selected = [["delete"], ["delete", "create"], rng.choice([["update"], ["create"]])]
    rng.shuffle(selected)
    return [_change(seed=seed, index=index, actions=actions_value, rng=rng) for index, actions_value in enumerate(selected)]


def _change(*, seed: str, index: int, actions: list[str], rng: random.Random) -> dict[str, Any]:
    resource_type = rng.choice(["aws_s3_bucket", "aws_iam_role", "aws_security_group", "aws_lb", "aws_dynamodb_table"])
    token = hashlib.sha256(f"{seed}:{index}:{resource_type}:{','.join(actions)}".encode("utf-8")).hexdigest()[:8]
    name = f"smoke_{token}"
    return {
        "address": f"{resource_type}.{name}",
        "provider_name": "registry.terraform.io/hashicorp/aws",
        "type": resource_type,
        "change": {"actions": actions},
    }


def _action_mix(changes: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"create": 0, "update": 0, "destroy": 0, "replace": 0, "no-op": 0}
    for change in changes:
        action = _action_name(change)
        counts[action] = int(counts.get(action, 0)) + 1
    return counts


def _unsupported_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    unsupported: list[dict[str, Any]] = []
    for index, row in enumerate(payload.get("resource_changes") or []):
        if not isinstance(row, dict):
            unsupported.append({"index": index, "reason": "resource_change_not_object"})
            continue
        if _action_name(row) == "unsupported":
            unsupported.append({"index": index, "actions": row.get("change", {}).get("actions") if isinstance(row.get("change"), dict) else None})
    return unsupported


def _action_name(change: dict[str, Any]) -> str:
    change_payload = change.get("change") if isinstance(change, dict) else None
    actions = change_payload.get("actions") if isinstance(change_payload, dict) else None
    normalized = [str(item).strip().lower() for item in actions or [] if str(item).strip()]
    if normalized in (["create"], ["update"], ["no-op"], ["noop"]):
        return "no-op" if normalized == ["noop"] else normalized[0]
    if normalized == ["delete"]:
        return "destroy"
    if normalized in (["delete", "create"], ["create", "delete"]):
        return "replace"
    return "unsupported"


def _analysis_failures(analysis: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if analysis.get("analysis_complete") is not True:
        failures.append("deterministic_analysis_incomplete")
    for warning in analysis.get("warnings") or []:
        failures.append(str(warning))
    return failures


def _validation_report(
    observed_path: str,
    observed_result: str,
    failures: list[str],
    actual_verdict: str,
    analysis: dict[str, Any],
    unsupported_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if unsupported_actions and "unsupported_action_mix" not in failures:
        failures = [*failures, "unsupported_action_mix"]
        observed_path = "blocked"
        observed_result = "failure"
    return {
        "observed_path": observed_path,
        "observed_result": observed_result,
        "actual_verdict": actual_verdict,
        "blocking_reasons": failures,
        "unsupported_actions": unsupported_actions,
        "deterministic_analysis": analysis,
    }


def _require_seed(seed: str) -> str:
    normalized = str(seed or "").strip()
    if not normalized:
        raise ValueError("fixture_seed_required")
    return normalized
