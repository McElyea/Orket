from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

DEFAULT_OUT = "benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json"
DEFAULT_DRIFT = "benchmarks/results/protocol/local_prompting/live_verification/drift/profile_delta_report.json"
DEFAULT_TEMPLATE_AUDIT_ROOT = "benchmarks/results/protocol/local_prompting/live_verification/template_audit"
MANDATORY_PROFILE_FILES = {
    "strict_json_report": "strict_json_report.json",
    "tool_call_report": "tool_call_report.json",
    "anti_meta_report": "anti_meta_report.json",
    "sampling_capabilities": "sampling_capabilities.json",
    "render_verification": "render_verification.json",
    "capability_probe_method": "capability_probe_method.json",
    "suite_manifest": "suite_manifest.json",
    "tokenizer_identity": "tokenizer_identity.json",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate local prompting promotion readiness from conformance artifacts.",
    )
    parser.add_argument(
        "--profile-root",
        action="append",
        required=True,
        help="Path to conformance/<provider>/<profile_id> artifact directory (repeatable).",
    )
    parser.add_argument(
        "--drift-report",
        default=DEFAULT_DRIFT,
        help="Profile drift report path (LP-13).",
    )
    parser.add_argument(
        "--template-audit-root",
        default=DEFAULT_TEMPLATE_AUDIT_ROOT,
        help="Template audit root containing <profile_id>/audit_report.json and whitelist_decision.json.",
    )
    parser.add_argument(
        "--strict-json-threshold",
        type=float,
        default=0.98,
        help="Required strict_json pass-rate threshold.",
    )
    parser.add_argument(
        "--tool-call-threshold",
        type=float,
        default=0.99,
        help="Required tool_call pass-rate threshold.",
    )
    parser.add_argument(
        "--max-protocol-chatter-rate",
        type=float,
        default=0.02,
        help="Maximum allowed anti-meta protocol chatter rate.",
    )
    parser.add_argument(
        "--max-markdown-fence-rate",
        type=float,
        default=0.02,
        help="Maximum allowed anti-meta markdown-fence rate.",
    )
    parser.add_argument(
        "--min-strict-json-cases",
        type=int,
        default=1000,
        help="Minimum strict_json case count required for promotion evidence.",
    )
    parser.add_argument(
        "--min-tool-call-cases",
        type=int,
        default=500,
        help="Minimum tool_call case count required for promotion evidence.",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        default=True,
        help="Require capability_probe_method.mode == live (default: enabled).",
    )
    parser.add_argument(
        "--no-require-live",
        dest="require_live",
        action="store_false",
        help="Allow non-live capability probe mode.",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="Canonical readiness output path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless readiness is green.")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _normalize_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _gate(gate_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": gate_id, "passed": bool(passed), "detail": str(detail)}


def _discover_output_root(profile_root: Path) -> Path | None:
    for candidate in [profile_root, *profile_root.parents]:
        snapshot = candidate / "profiles" / "profile_registry_snapshot.json"
        if snapshot.exists():
            return candidate
    return None


def _profile_template_family(snapshot_payload: dict[str, Any], profile_id: str) -> str:
    rows = snapshot_payload.get("profiles")
    if not isinstance(rows, list):
        return "unknown"
    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = row.get("profile")
        if not isinstance(profile, dict):
            continue
        if str(profile.get("profile_id") or "") != profile_id:
            continue
        return str(profile.get("template_family") or "unknown")
    return "unknown"


def _load_profile_artifacts(profile_root: Path) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
    payloads: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    paths: dict[str, str] = {}
    for key, filename in MANDATORY_PROFILE_FILES.items():
        path = profile_root / filename
        if not path.exists():
            missing.append(filename)
            continue
        payloads[key] = _load_json(path)
        paths[key] = _normalize_path(path)
    return payloads, missing, paths


def _load_template_artifacts(template_audit_root: Path, profile_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, str]]:
    audit_path = template_audit_root / profile_id / "audit_report.json"
    whitelist_path = template_audit_root / profile_id / "whitelist_decision.json"
    audit_payload = _load_json(audit_path) if audit_path.exists() else None
    whitelist_payload = _load_json(whitelist_path) if whitelist_path.exists() else None
    paths = {
        "audit_report": _normalize_path(audit_path) if audit_path.exists() else "",
        "whitelist_decision": _normalize_path(whitelist_path) if whitelist_path.exists() else "",
    }
    return audit_payload, whitelist_payload, paths


def _evaluate_profile(
    *,
    profile_root: Path,
    template_audit_root: Path,
    strict_json_threshold: float,
    tool_call_threshold: float,
    max_protocol_chatter_rate: float,
    max_markdown_fence_rate: float,
    min_strict_json_cases: int,
    min_tool_call_cases: int,
    require_live: bool,
) -> dict[str, Any]:
    payloads, missing, artifact_paths = _load_profile_artifacts(profile_root)
    gates: list[dict[str, Any]] = []
    errors: list[str] = []

    if missing:
        gates.append(_gate("G1_artifact_set", False, f"missing={','.join(sorted(missing))}"))
        errors.append(f"missing_required_artifacts:{','.join(sorted(missing))}")
        return {
            "profile_root": _normalize_path(profile_root),
            "ready": False,
            "gates": gates,
            "errors": errors,
            "artifact_paths": artifact_paths,
        }

    strict_json = payloads["strict_json_report"]
    tool_call = payloads["tool_call_report"]
    anti_meta = payloads["anti_meta_report"]
    suite_manifest = payloads["suite_manifest"]
    probe_method = payloads["capability_probe_method"]

    profile_id = str(strict_json.get("profile_id") or "").strip()
    provider = str(strict_json.get("provider") or "").strip()
    model = str(strict_json.get("model") or "").strip()

    for key, payload in payloads.items():
        payload_profile = str(payload.get("profile_id") or "").strip()
        if payload_profile and profile_id and payload_profile != profile_id:
            errors.append(f"profile_id_mismatch:{key}:{payload_profile}!={profile_id}")
        payload_provider = str(payload.get("provider") or "").strip()
        if payload_provider and provider and payload_provider != provider:
            errors.append(f"provider_mismatch:{key}:{payload_provider}!={provider}")
        payload_model = str(payload.get("model") or "").strip()
        if payload_model and model and payload_model != model:
            errors.append(f"model_mismatch:{key}:{payload_model}!={model}")

    output_root = _discover_output_root(profile_root)
    snapshot_payload: dict[str, Any] = {}
    template_family = "unknown"
    if output_root is None:
        errors.append("profile_registry_snapshot_not_found")
    else:
        snapshot_path = output_root / "profiles" / "profile_registry_snapshot.json"
        snapshot_payload = _load_json(snapshot_path)
        template_family = _profile_template_family(snapshot_payload, profile_id)
        artifact_paths["profile_registry_snapshot"] = _normalize_path(snapshot_path)
        error_registry_path = output_root / "profiles" / "error_code_registry_snapshot.json"
        enabled_pack_path = output_root / "profiles" / "enabled_pack.json"
        artifact_paths["error_code_registry_snapshot"] = _normalize_path(error_registry_path)
        artifact_paths["enabled_pack"] = _normalize_path(enabled_pack_path)
        gates.append(
            _gate(
                "G1_artifact_set",
                error_registry_path.exists() and enabled_pack_path.exists(),
                f"error_code_registry_snapshot={error_registry_path.exists()} enabled_pack={enabled_pack_path.exists()}",
            )
        )

    strict_total = _as_int(strict_json.get("total_cases"))
    tool_total = _as_int(tool_call.get("total_cases"))
    promotion_suite_ok = (
        str(suite_manifest.get("suite") or "").strip().lower() == "promotion"
        and strict_total >= int(min_strict_json_cases)
        and tool_total >= int(min_tool_call_cases)
    )
    gates.append(
        _gate(
            "G2_promotion_suite_volume",
            promotion_suite_ok,
            f"suite={suite_manifest.get('suite')} strict_total={strict_total} tool_total={tool_total}",
        )
    )

    strict_pass_rate = _as_float(strict_json.get("pass_rate"))
    strict_ok = bool(strict_json.get("strict_ok", False)) and strict_pass_rate >= strict_json_threshold
    gates.append(_gate("G3_strict_json_threshold", strict_ok, f"pass_rate={strict_pass_rate:.6f} threshold={strict_json_threshold:.6f}"))

    tool_pass_rate = _as_float(tool_call.get("pass_rate"))
    tool_ok = bool(tool_call.get("strict_ok", False)) and tool_pass_rate >= tool_call_threshold
    gates.append(_gate("G4_tool_call_threshold", tool_ok, f"pass_rate={tool_pass_rate:.6f} threshold={tool_call_threshold:.6f}"))

    protocol_chatter_rate = _as_float(anti_meta.get("protocol_chatter_rate"))
    markdown_fence_rate = _as_float(anti_meta.get("markdown_fence_rate"))
    anti_meta_ok = bool(anti_meta.get("strict_ok", False)) and protocol_chatter_rate <= max_protocol_chatter_rate and markdown_fence_rate <= max_markdown_fence_rate
    gates.append(
        _gate(
            "G5_anti_meta_threshold",
            anti_meta_ok,
            (
                f"protocol_chatter_rate={protocol_chatter_rate:.6f} max={max_protocol_chatter_rate:.6f} "
                f"markdown_fence_rate={markdown_fence_rate:.6f} max={max_markdown_fence_rate:.6f}"
            ),
        )
    )

    probe_mode = str(probe_method.get("mode") or "").strip().lower()
    probe_name = str(probe_method.get("method") or "").strip()
    live_ok = (not require_live) or probe_mode == "live"
    primary_path_ok = probe_name in {"runtime_response_metadata", "request_payload_hash"}
    gates.append(
        _gate(
            "G6_live_primary_path",
            live_ok and primary_path_ok,
            f"mode={probe_mode or '<empty>'} method={probe_name or '<empty>'}",
        )
    )

    failure_summary_path = profile_root / "failure_summary.json"
    failure_total = 0
    if failure_summary_path.exists():
        failure_summary = _load_json(failure_summary_path)
        artifact_paths["failure_summary"] = _normalize_path(failure_summary_path)
        failure_total = _as_int(failure_summary.get("total_failures"))
    else:
        failure_total = sum(int(value or 0) for value in dict(strict_json.get("failure_families") or {}).values())
        failure_total += sum(int(value or 0) for value in dict(tool_call.get("failure_families") or {}).values())
    gates.append(_gate("G7_failure_summary_clear", failure_total == 0, f"total_failures={failure_total}"))

    template_gate_pass = True
    template_detail = "not_required"
    if template_family != "openai_messages":
        audit_payload, whitelist_payload, template_paths = _load_template_artifacts(template_audit_root, profile_id)
        artifact_paths.update({k: v for k, v in template_paths.items() if v})
        audit_pass = bool(audit_payload and str(audit_payload.get("decision") or "").strip().lower() == "pass")
        whitelist_pass = bool(whitelist_payload and bool(whitelist_payload.get("promotion_allowed", False)))
        template_gate_pass = audit_pass or whitelist_pass
        template_detail = f"template_family={template_family} audit_pass={audit_pass} whitelist_pass={whitelist_pass}"
    gates.append(_gate("G8_template_audit_whitelist", template_gate_pass, template_detail))

    if errors:
        gates.append(_gate("G0_consistency", False, ";".join(errors)))
    else:
        gates.append(_gate("G0_consistency", True, "provider/model/profile consistent"))

    ready = all(bool(gate["passed"]) for gate in gates)
    return {
        "profile_id": profile_id,
        "provider": provider,
        "model": model,
        "template_family": template_family,
        "profile_root": _normalize_path(profile_root),
        "ready": ready,
        "gates": gates,
        "errors": errors,
        "artifact_paths": artifact_paths,
        "metrics": {
            "strict_json_total_cases": strict_total,
            "strict_json_pass_rate": round(strict_pass_rate, 6),
            "tool_call_total_cases": tool_total,
            "tool_call_pass_rate": round(tool_pass_rate, 6),
            "protocol_chatter_rate": round(protocol_chatter_rate, 6),
            "markdown_fence_rate": round(markdown_fence_rate, 6),
            "failure_total": failure_total,
        },
    }


def evaluate_promotion_readiness(
    *,
    profile_roots: list[Path],
    drift_report: Path,
    template_audit_root: Path,
    strict_json_threshold: float,
    tool_call_threshold: float,
    max_protocol_chatter_rate: float,
    max_markdown_fence_rate: float,
    min_strict_json_cases: int,
    min_tool_call_cases: int,
    require_live: bool,
) -> dict[str, Any]:
    profiles = [
        _evaluate_profile(
            profile_root=path,
            template_audit_root=template_audit_root,
            strict_json_threshold=strict_json_threshold,
            tool_call_threshold=tool_call_threshold,
            max_protocol_chatter_rate=max_protocol_chatter_rate,
            max_markdown_fence_rate=max_markdown_fence_rate,
            min_strict_json_cases=min_strict_json_cases,
            min_tool_call_cases=min_tool_call_cases,
            require_live=require_live,
        )
        for path in profile_roots
    ]

    drift_payload: dict[str, Any] = {}
    drift_ok = False
    drift_errors: list[str] = []
    if drift_report.exists():
        drift_payload = _load_json(drift_report)
        drift_ok = not bool(drift_payload.get("changed", True))
        if not drift_ok:
            drift_errors.append("profile_drift_changed=true")
    else:
        drift_errors.append("drift_report_missing")

    all_profiles_ready = all(bool(row.get("ready", False)) for row in profiles)
    gates = [
        _gate("G9_drift_gate", drift_ok, f"path={_normalize_path(drift_report)} exists={drift_report.exists()} changed={bool(drift_payload.get('changed', True)) if drift_payload else 'unknown'}"),
        _gate("G10_all_profiles_ready", all_profiles_ready, f"ready_profiles={sum(1 for row in profiles if row.get('ready'))}/{len(profiles)}"),
    ]

    ready = all_profiles_ready and drift_ok
    errors = drift_errors + [f"profile_not_ready:{row.get('profile_id') or row.get('profile_root')}" for row in profiles if not bool(row.get("ready", False))]
    return {
        "schema_version": "local_prompting_promotion_readiness.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "parameters": {
            "strict_json_threshold": strict_json_threshold,
            "tool_call_threshold": tool_call_threshold,
            "max_protocol_chatter_rate": max_protocol_chatter_rate,
            "max_markdown_fence_rate": max_markdown_fence_rate,
            "min_strict_json_cases": min_strict_json_cases,
            "min_tool_call_cases": min_tool_call_cases,
            "require_live": require_live,
            "profile_roots": [_normalize_path(path) for path in profile_roots],
            "drift_report": _normalize_path(drift_report),
            "template_audit_root": _normalize_path(template_audit_root),
        },
        "profiles": profiles,
        "drift": {
            "path": _normalize_path(drift_report),
            "exists": drift_report.exists(),
            "changed": bool(drift_payload.get("changed", True)) if drift_payload else None,
        },
        "gates": gates,
        "ready": ready,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    profile_roots = [Path(str(token)).resolve() for token in list(args.profile_root or [])]
    payload = evaluate_promotion_readiness(
        profile_roots=profile_roots,
        drift_report=Path(str(args.drift_report)).resolve(),
        template_audit_root=Path(str(args.template_audit_root)).resolve(),
        strict_json_threshold=float(args.strict_json_threshold),
        tool_call_threshold=float(args.tool_call_threshold),
        max_protocol_chatter_rate=float(args.max_protocol_chatter_rate),
        max_markdown_fence_rate=float(args.max_markdown_fence_rate),
        min_strict_json_cases=max(1, int(args.min_strict_json_cases)),
        min_tool_call_cases=max(1, int(args.min_tool_call_cases)),
        require_live=bool(args.require_live),
    )
    write_payload_with_diff_ledger(Path(str(args.out)).resolve(), payload)
    if bool(args.strict) and not bool(payload.get("ready", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
