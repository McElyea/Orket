from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from orket.application.services.trust_handoff_contract import (
    BUNDLE_PATH,
    BUNDLE_SCHEMA_VERSION,
    COMMITTED_OUTPUT_PATH,
    COMPARE_SCOPE,
    COMPATIBILITY_SCOPE_PATH,
    LEDGER_EXPORT_PATH,
    PACKAGE_SCHEMA_VERSION,
    SCOPE_SCHEMA_VERSION,
    SOURCE_WITNESS_BUNDLE_PATH,
    canonical_json_digest,
    envelope_digest,
    load_json_bytes,
    package_digest,
    scope_digest,
    sha256_bytes,
)

DEFAULT_SOURCE_PACKAGE_CANDIDATES = (
    Path("benchmarks/results/proof/outward_run_witness_package.v1"),
    Path("tests/proof_fixtures/outward_run/base_approved_package"),
)


class TrustHandoffEmissionError(RuntimeError):
    pass


def emit_trust_handoff_package(
    *,
    source_run_id: str,
    target_agent_id: str,
    scope_id: str,
    out_dir: Path,
    source_package: Path | None = None,
) -> dict[str, Any]:
    source_root = _resolve_source_package(source_run_id, source_package)
    source_ledger = _load_source_json(source_root / "ledger_export.json")
    source_witness = _load_source_json(source_root / "outward_witness_bundle.json")
    source_ledger_path = source_root / "ledger_export.json"
    source_witness_path = source_root / "outward_witness_bundle.json"
    committed_output = (source_root / "artifacts" / "committed_output").read_bytes()
    _validate_source(source_run_id, source_ledger, source_witness)

    output_dir = out_dir.resolve()
    _reset_output_dir(output_dir)
    (output_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    ledger_bytes = source_ledger_path.read_bytes()
    witness_bytes = source_witness_path.read_bytes()
    (output_dir / LEDGER_EXPORT_PATH).write_bytes(ledger_bytes)
    (output_dir / SOURCE_WITNESS_BUNDLE_PATH).write_bytes(witness_bytes)
    (output_dir / COMMITTED_OUTPUT_PATH).write_bytes(committed_output)

    source_policy_digest = str(source_witness["run_authority"]["policy_overrides_digest"])
    source_agent_id = _source_agent_id(source_ledger)
    scope = _build_scope(scope_id, source_policy_digest, source_agent_id)
    _write_json(output_dir / COMPATIBILITY_SCOPE_PATH, scope)

    bundle = _build_bundle(
        source_run_id=source_run_id,
        target_agent_id=target_agent_id,
        scope_id=scope_id,
        source_agent_id=source_agent_id,
        source_ledger=source_ledger,
        source_witness=source_witness,
        ledger_bytes=ledger_bytes,
        witness_bytes=witness_bytes,
        committed_output=committed_output,
    )
    _write_json(output_dir / BUNDLE_PATH, bundle)
    manifest = _build_manifest(output_dir, source_run_id=source_run_id, target_agent_id=target_agent_id)
    _write_json(output_dir / "manifest.json", manifest)
    return {
        "package_path": str(output_dir),
        "source_run_id": source_run_id,
        "target_agent_id": target_agent_id,
        "scope_id": scope_id,
        "envelope_digest": bundle["envelope_digest"],
        "package_digest": manifest["package_digest"],
    }


def _resolve_source_package(source_run_id: str, source_package: Path | None) -> Path:
    candidates = (source_package,) if source_package is not None else DEFAULT_SOURCE_PACKAGE_CANDIDATES
    for candidate in candidates:
        if candidate is None:
            continue
        root = candidate.resolve()
        if not root.exists():
            continue
        try:
            witness = _load_source_json(root / "outward_witness_bundle.json")
        except (OSError, ValueError):
            continue
        if witness.get("run_id") == source_run_id:
            return root
    raise TrustHandoffEmissionError(f"source witness package not found for run_id={source_run_id}")


def _validate_source(source_run_id: str, ledger: dict[str, Any], witness: dict[str, Any]) -> None:
    if ledger.get("schema_version") != "ledger_export.v1" or ledger.get("export_scope") != "all":
        raise TrustHandoffEmissionError("source_ledger_export_must_be_full_ledger_export_v1")
    if ledger.get("run_id") != source_run_id or witness.get("run_id") != source_run_id:
        raise TrustHandoffEmissionError("source_run_id_drift")
    if any(str(event.get("event_type") or "").startswith("trust_handoff_") for event in ledger.get("events") or []):
        raise TrustHandoffEmissionError("source_ledger_contains_handoff_event")
    if not _first_event(ledger, "proposal_approved") or not _first_event(ledger, "commitment_recorded"):
        raise TrustHandoffEmissionError("source_run_missing_approval_or_commitment")
    refs = _committed_refs(witness)
    if len(refs) != 1 or refs[0].get("package_path") != COMMITTED_OUTPUT_PATH:
        raise TrustHandoffEmissionError("source_witness_committed_output_ref_missing")


def _build_bundle(
    *,
    source_run_id: str,
    target_agent_id: str,
    scope_id: str,
    source_agent_id: str,
    source_ledger: dict[str, Any],
    source_witness: dict[str, Any],
    ledger_bytes: bytes,
    witness_bytes: bytes,
    committed_output: bytes,
) -> dict[str, Any]:
    approval = _first_event(source_ledger, "proposal_approved")
    commitment = _first_event(source_ledger, "commitment_recorded")
    policy_digest = str(source_witness["run_authority"]["policy_overrides_digest"])
    artifact_ref = _committed_refs(source_witness)[0]
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"trust-handoff:{source_run_id}:{target_agent_id}:{scope_id}",
        "source_run_id": source_run_id,
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "handoff_policy_compatibility_scope_id": scope_id,
        "committed_output_digest": sha256_bytes(committed_output),
        "committed_output_path_hint": str(artifact_ref.get("path") or ""),
        "source_policy_digest": policy_digest,
        "source_policy_identity": {
            "policy_snapshot_id": f"policy_overrides:{policy_digest}",
            "policy_digest": policy_digest,
            "policy_family": "outward_policy_overrides",
            "policy_version": "v1",
        },
        "approval_record_digest": canonical_json_digest(approval.get("payload") or {}),
        "approval_id": str((approval.get("payload") or {}).get("proposal_id") or ""),
        "commitment_record_digest": canonical_json_digest(commitment.get("payload") or {}),
        "ledger_export_digest": sha256_bytes(ledger_bytes),
        "source_witness_bundle_digest": sha256_bytes(witness_bytes),
        "ledger_event_count": len([event for event in source_ledger.get("events") or [] if isinstance(event, dict)]),
        "compare_scope": COMPARE_SCOPE,
        "produced_at_iso": "",
    }
    bundle["envelope_digest"] = envelope_digest(bundle)
    return bundle


def _build_manifest(output_dir: Path, *, source_run_id: str, target_agent_id: str) -> dict[str, Any]:
    file_bytes = {
        BUNDLE_PATH: (output_dir / BUNDLE_PATH).read_bytes(),
        LEDGER_EXPORT_PATH: (output_dir / LEDGER_EXPORT_PATH).read_bytes(),
        SOURCE_WITNESS_BUNDLE_PATH: (output_dir / SOURCE_WITNESS_BUNDLE_PATH).read_bytes(),
        COMPATIBILITY_SCOPE_PATH: (output_dir / COMPATIBILITY_SCOPE_PATH).read_bytes(),
        COMMITTED_OUTPUT_PATH: (output_dir / COMMITTED_OUTPUT_PATH).read_bytes(),
    }
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": f"trust-handoff-package:{source_run_id}:{target_agent_id}",
        "source_run_id": source_run_id,
        "target_agent_id": target_agent_id,
        "bundle_path": BUNDLE_PATH,
        "ledger_export_path": LEDGER_EXPORT_PATH,
        "source_witness_bundle_path": SOURCE_WITNESS_BUNDLE_PATH,
        "compatibility_scope_path": COMPATIBILITY_SCOPE_PATH,
        "artifact_paths": {"committed_output": COMMITTED_OUTPUT_PATH},
        "issued_at_iso": "",
    }
    manifest["package_digest"] = package_digest(file_bytes)
    return manifest


def _build_scope(scope_id: str, policy_digest: str, source_agent_id: str) -> dict[str, Any]:
    scope = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "scope_id": scope_id,
        "admitted_source_policy_digests": [policy_digest],
        "admitted_source_agent_ids": [source_agent_id],
    }
    scope["scope_digest"] = scope_digest(scope)
    return scope


def _source_agent_id(ledger: dict[str, Any]) -> str:
    for event in ledger.get("events") or []:
        agent_id = str(event.get("agent_id") or "").strip()
        if agent_id and agent_id != "operator":
            return agent_id
    return "source-agent"


def _first_event(ledger: dict[str, Any], event_type: str) -> dict[str, Any]:
    for event in ledger.get("events") or []:
        if isinstance(event, dict) and event.get("event_type") == event_type:
            return event
    return {}


def _committed_refs(witness: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        ref
        for ref in witness.get("artifact_refs") or []
        if isinstance(ref, dict) and ref.get("artifact_role") == "committed_output" and ref.get("classification") == "authority"
    ]


def _load_source_json(path: Path) -> dict[str, Any]:
    return load_json_bytes(path.read_bytes())


def _canonical_file_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_bytes(_canonical_file_bytes(payload))


def _reset_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        resolved = output_dir.resolve()
        if resolved.anchor == str(resolved) or len(resolved.parts) < 3:
            raise TrustHandoffEmissionError("refusing_to_clean_unsafe_output_path")
        shutil.rmtree(resolved)
    output_dir.mkdir(parents=True, exist_ok=True)
