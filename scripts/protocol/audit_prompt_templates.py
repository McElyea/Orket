from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.protocol.local_prompting_template_gate import profile_row_hash
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from protocol.local_prompting_template_gate import profile_row_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.local_prompt_profiles import DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit local prompting templates for suspicious constructs.")
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH),
        help="Local prompt profile registry path.",
    )
    parser.add_argument(
        "--out-root",
        default="benchmarks/results/protocol/local_prompting",
        help="Base output root for template audit artifacts.",
    )
    parser.add_argument(
        "--whitelist",
        default="",
        help="Optional approvals JSON: profile_id, template_sha256, approved_by, approval_reference.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when non-whitelisted failures exist.")
    parser.add_argument("--profile-id", default="", help="Audit only this profile when supplied.")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _template_engine(profile: dict[str, Any]) -> str:
    variant = str(profile.get("template_variant") or "").lower()
    if "jinja" in variant:
        return "jinja2"
    if "go_template" in variant or "gotemplate" in variant:
        return "go_template"
    return "unknown"


def _scan_constructs(profile: dict[str, Any]) -> list[str]:
    variant = str(profile.get("template_variant") or "")
    source = str(profile.get("template_source") or "")
    template_text = str(profile.get("template_text") or "")
    blob = "\n".join([variant, source, template_text]).lower()
    detectors = {
        "conditional_message_branch": ["if message", "if user", "elif user"],
        "hidden_role_remap": ["role_map", "role remap", "system->user"],
        "undeclared_tool_injection": ["tool_manifest", "tool_instruction", "function_call_inject"],
        "regex_trigger_path": ["regex(", "re.search", "trigger_pattern", ".startswith(", ".endswith("],
        "jinja_globals_escape": ["{{ self.__init__.__globals__ }}", "__globals__"],
        "eval_escape": ["eval(", "exec(", "importlib"],
    }
    hits: list[str] = []
    for key, patterns in detectors.items():
        if any(pattern in blob for pattern in patterns):
            hits.append(key)
    # Fail closed on branches beyond the declared generation-prefix switch,
    # including aliases of message content and hidden role/tool conditions.
    branches = re.findall(r"{%[-+]?\s*(?:if|elif)\s+(.*?)\s*[-+]?%}", template_text, re.S)
    if any(branch.strip() != "add_generation_prompt" for branch in branches):
        hits.append("conditional_template_branch")
    expressions = re.findall(r"{{(.*?)}}", template_text, re.S)
    if any(re.search(r"\bif\b|\|\s*(?:select|reject|map)\b", expression) for expression in expressions):
        hits.append("conditional_template_expression")
    if re.search(r"{%[-+]?\s*(?:include|import|extends|from)\b", template_text):
        hits.append("external_template_dependency")
    return sorted(set(hits))


def _candidate_template_paths(row: dict[str, Any], profile: dict[str, Any], registry_path: Path) -> list[Path]:
    candidates: list[Path] = []
    for key in ("template_source_path", "template_path"):
        raw_values = []
        if key in profile:
            raw_values.append(profile.get(key))
        if key in row:
            raw_values.append(row.get(key))
        for raw in raw_values:
            token = str(raw or "").strip()
            if not token:
                continue
            path = Path(token)
            if not path.is_absolute():
                path = (registry_path.parent / path).resolve()
            candidates.append(path)
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _load_template_text(paths: list[Path]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    loaded_paths: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        chunks.append(path.read_bytes().decode("utf-8"))
        loaded_paths.append(str(path))
    return "\n".join(chunks), loaded_paths


def _approved_templates(path: str) -> list[dict[str, Any]]:
    raw = str(path or "").strip()
    if not raw:
        return []
    payload = _load_json(Path(raw).resolve())
    values = payload.get("approvals")
    if not isinstance(values, list):
        return []
    return [row for row in values if isinstance(row, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    registry_path = Path(str(args.registry)).resolve()
    registry = _load_json(registry_path)
    rows = registry.get("profiles")
    if not isinstance(rows, list):
        raise ValueError("registry profiles must be a list")

    approved = _approved_templates(str(args.whitelist))
    out_root = Path(str(args.out_root)).resolve() / "template_audit"
    failing_profiles: list[str] = []
    audited_profiles: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = row.get("profile")
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            continue
        if args.profile_id and profile_id != args.profile_id:
            continue
        template_family = str(profile.get("template_family") or "").strip()
        if template_family == "openai_messages":
            continue
        audited_profiles.append(profile_id)
        engine = _template_engine(profile)
        candidate_paths = _candidate_template_paths(row, profile, registry_path)
        template_blob, loaded_paths = _load_template_text(candidate_paths)
        scan_profile = dict(profile)
        if template_blob:
            scan_profile["template_text"] = f"{str(scan_profile.get('template_text') or '')}\n{template_blob}"
        constructs = _scan_constructs(scan_profile)
        if not template_blob:
            constructs.append("template_bytes_missing")
        template_hash = hashlib.sha256(template_blob.encode("utf-8")).hexdigest() if template_blob else ""
        passed = bool(template_blob) and not constructs
        audit = {
            "schema_version": "local_prompt_template_audit.v1",
            "profile_id": profile_id,
            "profile_row_sha256": profile_row_hash(row),
            "template_engine": engine,
            "template_family": template_family,
            "template_sources_loaded": loaded_paths,
            "template_sha256": template_hash,
            "template_bytes": len(template_blob.encode("utf-8")),
            "detected_constructs": constructs,
            "decision": "pass" if passed else "fail",
        }
        profile_dir = out_root / profile_id
        write_payload_with_diff_ledger(profile_dir / "audit_report.json", audit)

        approval = next((row for row in approved if row.get("profile_id") == profile_id
                         and row.get("template_sha256") == template_hash
                         and row.get("approval_reference") and row.get("approved_by")), {})
        whitelisted = bool(template_blob and approval)
        decision = {
            "schema_version": "local_prompt_template_whitelist_decision.v1",
            "profile_id": profile_id,
            "approved": whitelisted,
            "template_sha256": template_hash,
            "approval_reference": approval.get("approval_reference", ""),
            "approved_by": approval.get("approved_by", ""),
            "audit_decision": audit["decision"],
            "promotion_allowed": bool(passed or whitelisted),
        }
        write_payload_with_diff_ledger(profile_dir / "whitelist_decision.json", decision)
        if not decision["promotion_allowed"]:
            failing_profiles.append(profile_id)

    if bool(args.strict) and (failing_profiles or (args.profile_id and not audited_profiles)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
