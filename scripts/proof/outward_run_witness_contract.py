from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


PACKAGE_SCHEMA_VERSION = "outward_run_witness_package.v1"
BUNDLE_SCHEMA_VERSION = "outward_run.witness_bundle.v1"
REPORT_SCHEMA_VERSION = "outward_run_witness_report.v1"
INVARIANT_SCHEMA_VERSION = "outward_run_invariants.v1"
CAMPAIGN_SCHEMA_VERSION = "outward_run_campaign_report.v1"
COMPARE_SCOPE = "outward_run_write_file_approved_v1"
OPERATOR_SURFACE = "outward_run_witness_report.v1"

DEFAULT_BUNDLE_PATH = "outward_witness_bundle.json"
DEFAULT_LEDGER_EXPORT_PATH = "ledger_export.json"
DEFAULT_COMMITTED_ARTIFACT_PATH = "artifacts/committed_output"
DEFAULT_PROOF_OUTPUT = Path("benchmarks/results/proof/outward_run_witness_report.json")

BUNDLE_ONLY_BLOCKER = "package_required_for_proof"


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_diff_ledger(value: Any) -> Any:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
    return copied


def package_digest_material(manifest: dict[str, Any]) -> dict[str, Any]:
    material = dict(manifest)
    material.pop("package_digest", None)
    return material


def compute_package_digest(manifest: dict[str, Any]) -> str:
    return canonical_json_digest(package_digest_material(manifest))


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_object_required")
    return payload
