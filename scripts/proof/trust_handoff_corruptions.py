from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from orket.application.services.trust_handoff_contract import (
    BUNDLE_PATH,
    COMMITTED_OUTPUT_PATH,
    COMPATIBILITY_SCOPE_PATH,
    KEY_AUTHORITY_NOTE,
    LEDGER_EXPORT_PATH,
    SOURCE_WITNESS_BUNDLE_PATH,
    canonical_json_digest,
    envelope_digest,
    failure_class,
    load_json_bytes,
    package_digest,
    scope_digest,
    sha256_bytes,
    validate_report_conformance,
)
from orket.application.services.trust_handoff_verifier import verify_trust_handoff_package
from orket.core.domain.outward_ledger import GENESIS_CHAIN_HASH, chain_hash_for, event_group, event_hash_for
from orket.core.domain.outward_run_events import LedgerEvent

EXPECTED_FAILURES = {
    "MATH-CORR-001": "package_manifest_missing",
    "MATH-CORR-002": "package_digest_mismatch",
    "MATH-CORR-003": "bundle_schema_invalid",
    "MATH-CORR-004": "envelope_digest_mismatch",
    "MATH-CORR-005": "ledger_export_digest_mismatch",
    "MATH-CORR-006": "commitment_record_missing_or_drifted",
    "MATH-CORR-007": "approval_record_missing_or_drifted",
    "MATH-CORR-008": "approval_before_commitment_ordering_violated",
    "MATH-CORR-009": "post_approval_denial_present",
    "MATH-CORR-010": "committed_output_digest_mismatch",
    "MATH-CORR-011": "committed_output_digest_mismatch",
    "MATH-CORR-012": "committed_output_not_ledger_anchored",
    "MATH-CORR-013": "trust_handoff_policy_incompatible",
    "MATH-CORR-014": "trust_handoff_policy_incompatible",
    "MATH-CORR-015": "trust_handoff_agent_not_admitted",
    "MATH-CORR-016": "policy_identity_digest_mismatch",
    "MATH-CORR-017": "target_agent_id_mismatch",
    "MATH-CORR-018": "source_run_id_drift",
    "MATH-CORR-019": "ledger_export_partial_view",
    "MATH-CORR-020": "compatibility_scope_digest_mismatch",
    "MATH-CORR-021": "source_policy_digest_not_ledger_anchored",
    "MATH-CORR-022": "unexpected_package_file",
    "MATH-CORR-023": "package_ref_outside_package",
}


def run_trust_handoff_corruption_suite(*, base: Path) -> dict[str, Any]:
    base_report = verify_trust_handoff_package(base)
    rows: list[dict[str, Any]] = []
    tmp_root = base.parent / ".trust_handoff_corruption_tmp"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)
    try:
        for corruption_id, expected in EXPECTED_FAILURES.items():
            output = tmp_root / corruption_id
            shutil.copytree(base, output)
            _apply_corruption(output, corruption_id)
            report = verify_trust_handoff_package(output)
            rows.append(_row(corruption_id, expected, report))
        report_row = _report_conformance_row(base_report)
        rows.append(report_row)
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
    failed = [row for row in rows if row["status"] != "pass"]
    accepted_corruptions = [row for row in rows if row.get("observed_result") == "accepted"]
    return {
        "schema_version": "trust_handoff_corruption_report.v1",
        "base_package": str(base),
        "base_result": base_report.get("result"),
        "result": "accepted" if base_report.get("result") == "accepted" and not failed and not accepted_corruptions else "rejected",
        "implemented_count": len(EXPECTED_FAILURES),
        "report_conformance_count": 1,
        "failed_count": len(failed),
        "accepted_corruption_count": len(accepted_corruptions),
        "rows": rows,
    }


def _apply_corruption(root: Path, corruption_id: str) -> None:
    if corruption_id == "MATH-CORR-001":
        (root / "manifest.json").unlink()
    elif corruption_id == "MATH-CORR-002":
        (root / COMMITTED_OUTPUT_PATH).write_bytes(b"outer mutation")
    elif corruption_id == "MATH-CORR-003":
        bundle = _read_json(root, BUNDLE_PATH)
        bundle["schema_version"] = "broken"
        _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-004":
        bundle = _read_json(root, BUNDLE_PATH)
        bundle["source_agent_id"] = "mutated-after-envelope"
        _write_json(root, BUNDLE_PATH, bundle)
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-005":
        ledger = _read_json(root, LEDGER_EXPORT_PATH)
        ledger["run_id"] = "different-source-run"
        _write_json(root, LEDGER_EXPORT_PATH, _rehash_ledger(ledger))
        _rewrap_manifest(root)
    elif corruption_id in {"MATH-CORR-006", "MATH-CORR-007"}:
        event_type = "commitment_recorded" if corruption_id.endswith("006") else "proposal_approved"
        ledger = _without_event(_read_json(root, LEDGER_EXPORT_PATH), event_type)
        _write_json(root, LEDGER_EXPORT_PATH, ledger)
        _rewrap_ledger_authority(root)
    elif corruption_id == "MATH-CORR-008":
        ledger = _swap_events(_read_json(root, LEDGER_EXPORT_PATH), "proposal_approved", "commitment_recorded")
        _write_json(root, LEDGER_EXPORT_PATH, ledger)
        _rewrap_ledger_authority(root)
    elif corruption_id == "MATH-CORR-009":
        ledger = _insert_denial(_read_json(root, LEDGER_EXPORT_PATH))
        _write_json(root, LEDGER_EXPORT_PATH, ledger)
        _rewrap_ledger_authority(root)
    elif corruption_id == "MATH-CORR-010":
        (root / COMMITTED_OUTPUT_PATH).write_bytes(b"semantic output mutation")
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-011":
        _mutate_bundle(root, {"committed_output_digest": _digest_char("1")})
    elif corruption_id == "MATH-CORR-012":
        witness = _read_json(root, SOURCE_WITNESS_BUNDLE_PATH)
        _committed_ref(witness)["digest"] = _digest_char("2")
        _write_json(root, SOURCE_WITNESS_BUNDLE_PATH, witness)
        _rewrap_witness_authority(root)
    elif corruption_id == "MATH-CORR-013":
        scope = _read_json(root, COMPATIBILITY_SCOPE_PATH)
        scope["admitted_source_policy_digests"] = [_digest_char("3")]
        _write_json(root, COMPATIBILITY_SCOPE_PATH, _with_scope_digest(scope))
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-014":
        _set_policy_digest(root, _digest_char("4"), update_scope=False)
    elif corruption_id == "MATH-CORR-015":
        _mutate_bundle(root, {"source_agent_id": "agent:not-admitted"})
    elif corruption_id == "MATH-CORR-016":
        bundle = _read_json(root, BUNDLE_PATH)
        bundle["source_policy_identity"]["policy_digest"] = _digest_char("5")
        _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-017":
        _mutate_bundle(root, {"target_agent_id": "agent:wrong-target"})
    elif corruption_id == "MATH-CORR-018":
        _set_source_run_id_drift(root)
    elif corruption_id == "MATH-CORR-019":
        ledger = _read_json(root, LEDGER_EXPORT_PATH)
        ledger["export_scope"] = "partial_view"
        _write_json(root, LEDGER_EXPORT_PATH, ledger)
        _rewrap_bundle_ledger_only(root)
    elif corruption_id == "MATH-CORR-020":
        scope = _read_json(root, COMPATIBILITY_SCOPE_PATH)
        scope["admitted_source_policy_digests"] = []
        _write_json(root, COMPATIBILITY_SCOPE_PATH, scope)
        _rewrap_manifest(root)
    elif corruption_id == "MATH-CORR-021":
        _set_policy_digest(root, _digest_char("6"), update_scope=True, update_witness=False)
    elif corruption_id == "MATH-CORR-022":
        (root / "undeclared.txt").write_text("undeclared", encoding="utf-8")
    elif corruption_id == "MATH-CORR-023":
        manifest = _read_json(root, "manifest.json")
        manifest["bundle_path"] = "../outside.json"
        _write_json(root, "manifest.json", manifest)


def _set_policy_digest(root: Path, digest: str, *, update_scope: bool, update_witness: bool = True) -> None:
    bundle = _read_json(root, BUNDLE_PATH)
    bundle["source_policy_digest"] = digest
    bundle["source_policy_identity"]["policy_digest"] = digest
    if update_witness:
        witness = _read_json(root, SOURCE_WITNESS_BUNDLE_PATH)
        witness["run_authority"]["policy_overrides_digest"] = digest
        _write_json(root, SOURCE_WITNESS_BUNDLE_PATH, witness)
        bundle["source_witness_bundle_digest"] = sha256_bytes((root / SOURCE_WITNESS_BUNDLE_PATH).read_bytes())
    if update_scope:
        scope = _read_json(root, COMPATIBILITY_SCOPE_PATH)
        scope["admitted_source_policy_digests"] = [digest]
        _write_json(root, COMPATIBILITY_SCOPE_PATH, _with_scope_digest(scope))
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _set_source_run_id_drift(root: Path) -> None:
    bundle = _read_json(root, BUNDLE_PATH)
    witness = _read_json(root, SOURCE_WITNESS_BUNDLE_PATH)
    bundle["source_run_id"] = "source-run-drift"
    witness["run_id"] = "source-run-drift"
    _write_json(root, SOURCE_WITNESS_BUNDLE_PATH, witness)
    bundle["source_witness_bundle_digest"] = sha256_bytes((root / SOURCE_WITNESS_BUNDLE_PATH).read_bytes())
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _mutate_bundle(root: Path, updates: dict[str, Any]) -> None:
    bundle = _read_json(root, BUNDLE_PATH)
    bundle.update(updates)
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _rewrap_ledger_authority(root: Path) -> None:
    ledger_digest = sha256_bytes((root / LEDGER_EXPORT_PATH).read_bytes())
    witness = _read_json(root, SOURCE_WITNESS_BUNDLE_PATH)
    witness["ledger_evidence"]["ledger_export_digest"] = ledger_digest
    _write_json(root, SOURCE_WITNESS_BUNDLE_PATH, witness)
    _rewrap_bundle_ledger_only(root)
    bundle = _read_json(root, BUNDLE_PATH)
    bundle["source_witness_bundle_digest"] = sha256_bytes((root / SOURCE_WITNESS_BUNDLE_PATH).read_bytes())
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _rewrap_bundle_ledger_only(root: Path) -> None:
    ledger = _read_json(root, LEDGER_EXPORT_PATH)
    bundle = _read_json(root, BUNDLE_PATH)
    bundle["ledger_export_digest"] = sha256_bytes((root / LEDGER_EXPORT_PATH).read_bytes())
    bundle["ledger_event_count"] = len([event for event in ledger.get("events") or [] if isinstance(event, dict)])
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _rewrap_witness_authority(root: Path) -> None:
    bundle = _read_json(root, BUNDLE_PATH)
    bundle["source_witness_bundle_digest"] = sha256_bytes((root / SOURCE_WITNESS_BUNDLE_PATH).read_bytes())
    _write_json(root, BUNDLE_PATH, _with_envelope(bundle))
    _rewrap_manifest(root)


def _rewrap_manifest(root: Path) -> None:
    manifest = _read_json(root, "manifest.json")
    files = {
        BUNDLE_PATH: (root / BUNDLE_PATH).read_bytes(),
        LEDGER_EXPORT_PATH: (root / LEDGER_EXPORT_PATH).read_bytes(),
        SOURCE_WITNESS_BUNDLE_PATH: (root / SOURCE_WITNESS_BUNDLE_PATH).read_bytes(),
        COMPATIBILITY_SCOPE_PATH: (root / COMPATIBILITY_SCOPE_PATH).read_bytes(),
        COMMITTED_OUTPUT_PATH: (root / COMMITTED_OUTPUT_PATH).read_bytes(),
    }
    manifest["package_digest"] = package_digest(files)
    _write_json(root, "manifest.json", manifest)


def _row(corruption_id: str, expected: str, report: dict[str, Any]) -> dict[str, Any]:
    observed = str(report.get("rejection_reason") or "")
    return {
        "corruption_id": corruption_id,
        "status": "pass" if report.get("result") == "rejected" and observed == expected else "fail",
        "expected_failure_code": expected,
        "expected_failure_class": failure_class(expected),
        "observed_result": report.get("result"),
        "observed_rejection_reason": observed,
        "observed_rejection_class": report.get("rejection_class"),
    }


def _report_conformance_row(base_report: dict[str, Any]) -> dict[str, Any]:
    mutated = dict(base_report)
    mutated.pop("key_authority_note", None)
    conformance = validate_report_conformance(mutated)
    expected = "key_authority_note_missing"
    return {
        "corruption_id": "MATH-REPORT-001",
        "status": "pass" if conformance.get("rejection_reason") == expected else "fail",
        "expected_failure_code": expected,
        "expected_failure_class": failure_class(expected),
        "observed_result": conformance.get("result"),
        "observed_rejection_reason": conformance.get("rejection_reason"),
        "observed_rejection_class": conformance.get("rejection_class"),
    }


def _without_event(ledger: dict[str, Any], event_type: str) -> dict[str, Any]:
    copied = copy.deepcopy(ledger)
    copied["events"] = [event for event in copied.get("events") or [] if event.get("event_type") != event_type]
    return _rehash_ledger(copied)


def _swap_events(ledger: dict[str, Any], first: str, second: str) -> dict[str, Any]:
    copied = copy.deepcopy(ledger)
    events = list(copied.get("events") or [])
    first_index = next(index for index, event in enumerate(events) if event.get("event_type") == first)
    second_index = next(index for index, event in enumerate(events) if event.get("event_type") == second)
    events[first_index], events[second_index] = events[second_index], events[first_index]
    copied["events"] = events
    return _rehash_ledger(copied)


def _insert_denial(ledger: dict[str, Any]) -> dict[str, Any]:
    copied = copy.deepcopy(ledger)
    events = list(copied.get("events") or [])
    approval_index = next(index for index, event in enumerate(events) if event.get("event_type") == "proposal_approved")
    approval = events[approval_index]
    denial = copy.deepcopy(approval)
    denial["event_id"] = f"{approval['event_id']}:denied-after-approval"
    denial["event_type"] = "proposal_denied"
    denial["event_group"] = "decisions"
    denial["payload"]["decision"] = "deny"
    denial["payload"]["status"] = "denied"
    events.insert(approval_index + 1, denial)
    copied["events"] = events
    return _rehash_ledger(copied)


def _rehash_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    copied = copy.deepcopy(ledger)
    previous = GENESIS_CHAIN_HASH
    for position, event in enumerate(copied.get("events") or [], start=1):
        event["position"] = position
        event["event_group"] = event_group(str(event.get("event_type") or ""))
        event["previous_chain_hash"] = previous
        event_hash = event_hash_for(
            LedgerEvent(
                event_id=str(event.get("event_id") or ""),
                event_type=str(event.get("event_type") or ""),
                run_id=str(event.get("run_id") or ""),
                turn=event.get("turn"),
                agent_id=event.get("agent_id"),
                at=str(event.get("at") or ""),
                payload=dict(event.get("payload") or {}),
            )
        )
        event["event_hash"] = event_hash
        event["chain_hash"] = chain_hash_for(previous, event_hash)
        previous = event["chain_hash"]
    copied["canonical"]["event_count"] = len(copied.get("events") or [])
    copied["canonical"]["ledger_hash"] = previous
    return copied


def _committed_ref(witness: dict[str, Any]) -> dict[str, Any]:
    for ref in witness.get("artifact_refs") or []:
        if isinstance(ref, dict) and ref.get("artifact_role") == "committed_output":
            return ref
    raise RuntimeError("committed_output_ref_missing")


def _with_envelope(bundle: dict[str, Any]) -> dict[str, Any]:
    bundle["envelope_digest"] = envelope_digest(bundle)
    return bundle


def _with_scope_digest(scope: dict[str, Any]) -> dict[str, Any]:
    scope["scope_digest"] = scope_digest(scope)
    return scope


def _digest_char(char: str) -> str:
    return char * 64


def _read_json(root: Path, rel: str) -> dict[str, Any]:
    return load_json_bytes((root / rel).read_bytes())


def _write_json(root: Path, rel: str, payload: dict[str, Any]) -> None:
    (root / rel).write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
