from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path
from typing import Any, Sequence

from scripts.proof.trusted_run_witness_contract import relative_to_repo, stable_json_digest

NON_INTERFERENCE_SCHEMA_VERSION = "offline_verifier_non_interference.v1"
INSPECTED_MODULES = (
    "scripts/proof/offline_trusted_run_verifier.py",
    "scripts/proof/trusted_run_witness_contract.py",
    "scripts/proof/trusted_run_invariant_model.py",
    "scripts/proof/control_plane_witness_substrate.py",
    "scripts/proof/trusted_run_non_interference.py",
    "scripts/proof/trusted_scope_family_support.py",
    "scripts/proof/trusted_scope_family_claims.py",
    "scripts/proof/trusted_scope_family_common.py",
    "scripts/proof/trusted_repo_change_offline.py",
    "scripts/proof/trusted_repo_change_verifier.py",
    "scripts/proof/governed_change_packet_contract.py",
    "scripts/proof/governed_change_packet_trusted_kernel.py",
    "scripts/proof/governed_change_packet_verifier.py",
    "scripts/proof/trusted_terraform_plan_decision_offline.py",
    "scripts/proof/trusted_terraform_plan_decision_verifier.py",
    "scripts/proof/verify_offline_trusted_run_claim.py",
    "scripts/proof/verify_governed_change_packet.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "orket",
    "subprocess",
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "sqlite3",
    "openai",
)
FORBIDDEN_EXACT_CALLS = {
    "open",
    "exec",
    "eval",
    "compile",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
}
FORBIDDEN_ATTRIBUTE_CALLS = {
    "write_text",
    "write_bytes",
    "mkdir",
    "touch",
    "unlink",
    "rmdir",
}
ALLOWED_WRITER_CALLS = {"write_payload_with_diff_ledger", "write_json_with_diff_ledger"}

_NON_INTERFERENCE_CACHE: dict[str, Any] | None = None


def evaluate_offline_verifier_non_interference(
    module_paths: Sequence[str | Path] | None = None,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    global _NON_INTERFERENCE_CACHE
    if module_paths is None and use_cache and _NON_INTERFERENCE_CACHE is not None:
        return copy.deepcopy(_NON_INTERFERENCE_CACHE)

    resolved_paths = [_resolve_repo_path(item) for item in (module_paths or INSPECTED_MODULES)]
    file_reports = [_inspect_module(path) for path in resolved_paths]
    forbidden_import_hits = [hit for report in file_reports for hit in report["forbidden_import_hits"]]
    forbidden_call_hits = [hit for report in file_reports for hit in report["forbidden_call_hits"]]
    cli_reports = [report for report in file_reports if report["relative_path"] == "scripts/proof/verify_offline_trusted_run_claim.py"]
    cli_writer_ok = bool(cli_reports) and all(
        report["unexpected_writer_calls"] == [] and bool(report["allowed_writer_calls"])
        for report in cli_reports
    )
    checks = [
        _check(
            "non_interference_no_runtime_or_network_imports",
            not forbidden_import_hits,
            "offline verifier modules must not import runtime, provider, network, or subprocess surfaces",
        ),
        _check(
            "non_interference_no_direct_mutation_calls",
            not forbidden_call_hits,
            "offline verifier modules must not directly call filesystem, process, or durable-state mutation helpers",
        ),
        _check(
            "non_interference_cli_diff_ledger_boundary_only",
            cli_writer_ok,
            "the CLI may write only its declared diff-ledger JSON report",
        ),
    ]
    result = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    report = {
        "schema_version": NON_INTERFERENCE_SCHEMA_VERSION,
        "result": result,
        "checks": checks,
        "inspected_files": file_reports,
        "forbidden_import_hits": forbidden_import_hits,
        "forbidden_call_hits": forbidden_call_hits,
        "limitations": [
            "structural proof only over the inspected verifier modules and CLI surface",
            "does not prove Python, stdlib, or transitive dependency behavior beyond the inspected source files",
            "does not replace campaign or offline claim-ladder guards that fail closed when side-effect-free proof is missing",
        ],
    }
    report["non_interference_signature_digest"] = stable_json_digest(_non_interference_signature_material(report))
    if module_paths is None and use_cache:
        _NON_INTERFERENCE_CACHE = copy.deepcopy(report)
    return report


def _inspect_module(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: list[dict[str, Any]] = []
    forbidden_import_hits: list[dict[str, Any]] = []
    forbidden_call_hits: list[dict[str, Any]] = []
    allowed_writer_calls: list[str] = []
    unexpected_writer_calls: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"name": alias.name, "line": node.lineno})
                reason = _forbidden_import_reason(alias.name)
                if reason:
                    forbidden_import_hits.append(_import_hit(path, alias.name, node.lineno, reason))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append({"name": node.module, "line": node.lineno})
            reason = _forbidden_import_reason(node.module)
            if reason:
                forbidden_import_hits.append(_import_hit(path, node.module, node.lineno, reason))
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            attr_name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if call_name in ALLOWED_WRITER_CALLS:
                allowed_writer_calls.append(call_name)
            if call_name in FORBIDDEN_EXACT_CALLS:
                forbidden_call_hits.append(_call_hit(path, call_name, node.lineno, "forbidden exact call"))
            elif attr_name in FORBIDDEN_ATTRIBUTE_CALLS:
                forbidden_call_hits.append(_call_hit(path, call_name or attr_name, node.lineno, "forbidden mutating attribute call"))
            elif attr_name.startswith("write_") and call_name not in ALLOWED_WRITER_CALLS:
                unexpected_writer_calls.append(call_name or attr_name)

    if unexpected_writer_calls:
        for writer_call in unexpected_writer_calls:
            forbidden_call_hits.append(_call_hit(path, writer_call, 0, "unexpected writer helper"))

    return {
        "relative_path": relative_to_repo(path),
        "source_digest": _source_digest(source),
        "imports": imports,
        "allowed_writer_calls": sorted(set(allowed_writer_calls)),
        "unexpected_writer_calls": sorted(set(unexpected_writer_calls)),
        "forbidden_import_hits": forbidden_import_hits,
        "forbidden_call_hits": forbidden_call_hits,
    }


def _resolve_repo_path(item: str | Path) -> Path:
    path = Path(item)
    return path if path.is_absolute() else (Path(__file__).resolve().parents[2] / path).resolve()


def _forbidden_import_reason(module_name: str) -> str:
    for prefix in FORBIDDEN_IMPORT_PREFIXES:
        if module_name == prefix or module_name.startswith(f"{prefix}."):
            return prefix
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _import_hit(path: Path, module_name: str, line: int, reason: str) -> dict[str, Any]:
    return {
        "relative_path": relative_to_repo(path),
        "module": module_name,
        "line": line,
        "reason": reason,
    }


def _call_hit(path: Path, call_name: str, line: int, reason: str) -> dict[str, Any]:
    return {
        "relative_path": relative_to_repo(path),
        "call": call_name,
        "line": line,
        "reason": reason,
    }


def _source_digest(source: str) -> str:
    return "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()


def _check(check_id: str, passed: bool, basis: str) -> dict[str, str]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "basis": basis,
    }


def _non_interference_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": NON_INTERFERENCE_SCHEMA_VERSION,
        "result": report.get("result"),
        "checks": {item["id"]: item["status"] for item in report.get("checks") or []},
        "files": {
            item["relative_path"]: {
                "source_digest": item["source_digest"],
                "allowed_writer_calls": item["allowed_writer_calls"],
                "unexpected_writer_calls": item["unexpected_writer_calls"],
                "forbidden_import_count": len(item["forbidden_import_hits"]),
                "forbidden_call_count": len(item["forbidden_call_hits"]),
            }
            for item in report.get("inspected_files") or []
        },
    }
