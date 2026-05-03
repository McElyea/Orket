#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.core.domain.outward_ledger import chain_hash_for, event_group, event_hash_for
from orket.core.domain.outward_run_events import LedgerEvent
from scripts.proof.outward_run_witness_contract import compute_package_digest, file_sha256


EXPECTED_FAILURES: dict[str, str] = {
    "ORP-CORR-001": "bundle_schema_missing_or_unsupported",
    "ORP-CORR-002": "bundle_schema_missing_or_unsupported",
    "ORP-CORR-003": "compare_scope_missing_or_unsupported",
    "ORP-CORR-004": "operator_surface_missing",
    "ORP-CORR-005": "package_manifest_missing",
    "ORP-CORR-006": "package_manifest_digest_mismatch",
    "ORP-CORR-007": "bundle_missing",
    "ORP-CORR-008": "package_ref_outside_package",
    "ORP-CORR-009": "package_ref_outside_package",
    "ORP-CORR-010": "effect_before_admission",
    "ORP-CORR-011": "effect_before_admission",
    "ORP-CORR-012": "run_authority_missing",
    "ORP-CORR-013": "run_id_drift",
    "ORP-CORR-020": "effect_before_approval",
    "ORP-CORR-021": "effect_before_approval",
    "ORP-CORR-022": "approval_authority_missing",
    "ORP-CORR-023": "approval_status_not_approved",
    "ORP-CORR-024": "tool_args_digest_drift",
    "ORP-CORR-025": "tool_args_digest_drift",
    "ORP-CORR-026": "tool_args_digest_drift",
    "ORP-CORR-040": "effect_evidence_missing",
    "ORP-CORR-041": "effect_evidence_missing",
    "ORP-CORR-042": "commitment_missing_after_effect",
    "ORP-CORR-043": "turn_not_completed_after_commitment",
    "ORP-CORR-050": "final_truth_missing",
    "ORP-CORR-051": "final_truth_missing",
    "ORP-CORR-052": "terminal_status_drift",
    "ORP-CORR-053": "terminal_status_drift",
    "ORP-CORR-054": "terminal_status_drift",
    "ORP-CORR-055": "commitment_missing_after_effect",
    "ORP-CORR-056": "commitment_missing_after_effect",
    "ORP-CORR-060": "ledger_chain_broken",
    "ORP-CORR-061": "ledger_chain_hash_mismatch",
    "ORP-CORR-062": "ledger_sequence_gap",
    "ORP-CORR-063": "ledger_chain_broken",
    "ORP-CORR-064": "ledger_chain_hash_mismatch",
    "ORP-CORR-065": "ledger_export_missing",
    "ORP-CORR-066": "ledger_export_digest_mismatch",
    "ORP-CORR-067": "ledger_chain_hash_mismatch",
    "ORP-CORR-069": "ledger_payload_bytes_missing",
    "ORP-CORR-070": "missing_authority_digest",
    "ORP-CORR-071": "missing_authority_digest",
    "ORP-CORR-072": "model_invocation_digest_drift",
    "ORP-CORR-073": "projection_substituted_for_authority",
    "ORP-CORR-074": "committed_artifact_missing",
    "ORP-CORR-075": "artifact_digest_mismatch",
    "ORP-CORR-080": "claim_tier_not_supported",
    "ORP-CORR-081": "claim_tier_not_supported",
    "ORP-CORR-082": "claim_tier_not_supported",
}

MISSING_FIXTURE_CORRUPTIONS = {
    "ORP-CORR-030": "base_denied_package_missing",
    "ORP-CORR-031": "base_policy_rejected_package_missing",
    "ORP-CORR-068": "base_denied_or_policy_rejected_package_missing",
}


def corrupt_package(*, base: Path, output: Path, corruption_id: str) -> dict[str, Any]:
    clean_id = str(corruption_id).strip()
    if clean_id in MISSING_FIXTURE_CORRUPTIONS:
        return {"result": "blocked", "corruption_id": clean_id, "failure_code": MISSING_FIXTURE_CORRUPTIONS[clean_id]}
    if clean_id not in EXPECTED_FAILURES:
        raise ValueError(f"unsupported corruption id: {clean_id}")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    shutil.copytree(base, output)
    _apply_corruption(output, clean_id)
    return {
        "result": "created",
        "corruption_id": clean_id,
        "expected_failure_code": EXPECTED_FAILURES[clean_id],
        "package": str(output),
    }


def _apply_corruption(root: Path, corruption_id: str) -> None:
    if corruption_id in {"ORP-CORR-001", "ORP-CORR-002", "ORP-CORR-003", "ORP-CORR-004"}:
        _mutate_bundle(root, lambda bundle: _schema_mutation(bundle, corruption_id))
    elif corruption_id == "ORP-CORR-005":
        (root / "manifest.json").unlink()
    elif corruption_id == "ORP-CORR-006":
        bundle = _read_bundle(root)
        bundle["corruption_marker"] = "digest-drift"
        _write_json(root / "outward_witness_bundle.json", bundle)
    elif corruption_id == "ORP-CORR-007":
        (root / "outward_witness_bundle.json").unlink()
    elif corruption_id == "ORP-CORR-008":
        _mutate_bundle(root, lambda bundle: bundle["package_refs"].update({"ledger_export_path": "../ledger_export.json"}))
    elif corruption_id == "ORP-CORR-009":
        _mutate_bundle(root, lambda bundle: bundle["artifact_refs"][0].update({"package_path": "../committed_output"}))
    elif corruption_id in {"ORP-CORR-010", "ORP-CORR-011", "ORP-CORR-020", "ORP-CORR-021", "ORP-CORR-040", "ORP-CORR-042", "ORP-CORR-043", "ORP-CORR-050", "ORP-CORR-052", "ORP-CORR-055", "ORP-CORR-056"}:
        _mutate_events(root, lambda events: _event_mutation(events, corruption_id))
    elif corruption_id in {"ORP-CORR-012", "ORP-CORR-013", "ORP-CORR-022", "ORP-CORR-023", "ORP-CORR-024", "ORP-CORR-025", "ORP-CORR-026", "ORP-CORR-041", "ORP-CORR-053", "ORP-CORR-054", "ORP-CORR-070", "ORP-CORR-071", "ORP-CORR-072", "ORP-CORR-073", "ORP-CORR-080", "ORP-CORR-081", "ORP-CORR-082"}:
        _mutate_bundle(root, lambda bundle: _bundle_mutation(bundle, corruption_id))
    elif corruption_id == "ORP-CORR-051":
        _mutate_events(root, lambda events: _set_terminal_outcome(events, "failed"))
    elif corruption_id in {"ORP-CORR-060", "ORP-CORR-062", "ORP-CORR-064", "ORP-CORR-069"}:
        _mutate_ledger_without_rehash(root, corruption_id)
    elif corruption_id == "ORP-CORR-061":
        _mutate_bundle(root, lambda bundle: bundle["ledger_evidence"].update({"ledger_hash": "bad-ledger-hash"}))
    elif corruption_id == "ORP-CORR-063":
        _mutate_bundle(root, lambda bundle: bundle.pop("ledger_evidence", None))
    elif corruption_id == "ORP-CORR-065":
        (root / "ledger_export.json").unlink()
    elif corruption_id == "ORP-CORR-066":
        _mutate_ledger_stale_bundle_digest(root)
    elif corruption_id == "ORP-CORR-067":
        _mutate_ledger_stale_bundle_hash(root)
    elif corruption_id == "ORP-CORR-074":
        (root / "artifacts" / "committed_output").unlink()
        _rewrite_manifest(root)
    elif corruption_id == "ORP-CORR-075":
        (root / "artifacts" / "committed_output").write_bytes(b"corrupted artifact bytes")
        _rewrite_manifest(root)
    else:
        raise ValueError(f"unsupported corruption id: {corruption_id}")


def _schema_mutation(bundle: dict[str, Any], corruption_id: str) -> None:
    if corruption_id == "ORP-CORR-001":
        bundle.pop("schema_version", None)
    elif corruption_id == "ORP-CORR-002":
        bundle["schema_version"] = "outward_run.witness_bundle.v0"
    elif corruption_id == "ORP-CORR-003":
        bundle["compare_scope"] = "unknown_scope"
    elif corruption_id == "ORP-CORR-004":
        bundle["operator_surface"] = "unsupported_surface"


def _bundle_mutation(bundle: dict[str, Any], corruption_id: str) -> None:
    if corruption_id == "ORP-CORR-012":
        bundle.pop("run_authority", None)
    elif corruption_id == "ORP-CORR-013":
        bundle["run_authority"]["run_id"] = "different-run-id"
    elif corruption_id == "ORP-CORR-022":
        bundle["approval_authority"] = []
    elif corruption_id == "ORP-CORR-023":
        bundle["approval_authority"][0]["status"] = "denied"
    elif corruption_id == "ORP-CORR-024":
        bundle["approval_authority"][0]["tool_args_digest"] = "drift"
    elif corruption_id == "ORP-CORR-025":
        bundle["effect_evidence"][0]["tool_args_digest"] = "drift"
    elif corruption_id == "ORP-CORR-026":
        bundle["approval_authority"][0]["tool_name"] = "read_file"
    elif corruption_id == "ORP-CORR-041":
        bundle["effect_evidence"] = []
    elif corruption_id == "ORP-CORR-053":
        bundle["run_authority"]["status"] = "failed"
    elif corruption_id == "ORP-CORR-054":
        bundle["run_authority"]["run_status"] = "failed"
    elif corruption_id == "ORP-CORR-070":
        bundle["run_authority"].pop("run_record_digest", None)
    elif corruption_id == "ORP-CORR-071":
        bundle["approval_authority"][0].pop("approval_record_digest", None)
    elif corruption_id == "ORP-CORR-072":
        bundle["model_invocation_evidence"][0]["model_invocation_digest"] = "drift"
    elif corruption_id == "ORP-CORR-073":
        bundle["projection_only_authority"] = True
        bundle["artifact_refs"][0]["classification"] = "support-only"
    elif corruption_id == "ORP-CORR-080":
        bundle["claim_tier_request"] = "outward_verifier_stable"
    elif corruption_id == "ORP-CORR-081":
        bundle["claim_tier_request"] = "outward_public_trust"
    elif corruption_id == "ORP-CORR-082":
        bundle["claim_tier_request"] = "outward_deterministic"


def _event_mutation(events: list[dict[str, Any]], corruption_id: str) -> None:
    if corruption_id == "ORP-CORR-010":
        _remove_first(events, "run_submitted")
    elif corruption_id == "ORP-CORR-011":
        events.append(events.pop(_index(events, "run_submitted")))
    elif corruption_id == "ORP-CORR-020":
        _remove_first(events, "proposal_approved")
    elif corruption_id == "ORP-CORR-021":
        item = events.pop(_index(events, "proposal_approved"))
        events.insert(_index(events, "tool_invoked") + 1, item)
    elif corruption_id == "ORP-CORR-040":
        _remove_first(events, "tool_invoked")
    elif corruption_id in {"ORP-CORR-042", "ORP-CORR-055"}:
        _remove_first(events, "commitment_recorded")
    elif corruption_id == "ORP-CORR-043":
        _remove_first(events, "turn_completed")
    elif corruption_id == "ORP-CORR-050":
        _remove_first(events, "run_completed")
    elif corruption_id == "ORP-CORR-052":
        duplicate = dict(events[_index(events, "run_completed")])
        duplicate["event_id"] = f"{duplicate['event_id']}:duplicate"
        events.append(duplicate)
    elif corruption_id == "ORP-CORR-056":
        events[_index(events, "commitment_recorded")]["payload"]["tool"] = "read_file"


def _set_terminal_outcome(events: list[dict[str, Any]], outcome: str) -> None:
    events[_index(events, "run_completed")]["payload"]["outcome"] = outcome


def _mutate_ledger_without_rehash(root: Path, corruption_id: str) -> None:
    ledger = _read_ledger(root)
    if corruption_id == "ORP-CORR-060":
        ledger["events"][1]["previous_chain_hash"] = "bad-previous-chain"
    elif corruption_id == "ORP-CORR-062":
        ledger["events"][1]["position"] = 1
    elif corruption_id == "ORP-CORR-064":
        ledger["canonical"]["ledger_hash"] = "bad-ledger-hash"
    elif corruption_id == "ORP-CORR-069":
        ledger["events"][0].pop("payload", None)
    _write_json(root / "ledger_export.json", ledger)
    _sync_ledger_digest_only(root)


def _mutate_ledger_stale_bundle_digest(root: Path) -> None:
    ledger = _read_ledger(root)
    ledger["events"][0]["payload"]["corrupted"] = True
    _write_json(root / "ledger_export.json", ledger)
    _rewrite_manifest(root)


def _mutate_ledger_stale_bundle_hash(root: Path) -> None:
    ledger = _read_ledger(root)
    ledger["canonical"]["ledger_hash"] = "different-ledger-hash"
    _write_json(root / "ledger_export.json", ledger)
    bundle = _read_bundle(root)
    bundle["ledger_evidence"]["ledger_export_digest"] = file_sha256(root / "ledger_export.json")
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _mutate_bundle(root: Path, mutator) -> None:
    bundle = _read_bundle(root)
    mutator(bundle)
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _mutate_events(root: Path, mutator) -> None:
    ledger = _read_ledger(root)
    events = [_base_event(event) for event in ledger["events"]]
    mutator(events)
    _write_ledger(root, events)
    _sync_ledger_evidence(root)


def _write_ledger(root: Path, events: list[dict[str, Any]]) -> None:
    previous = "GENESIS"
    exported: list[dict[str, Any]] = []
    for position, event_payload in enumerate(events, start=1):
        event = LedgerEvent(
            event_id=event_payload["event_id"],
            event_type=event_payload["event_type"],
            run_id=event_payload["run_id"],
            turn=event_payload["turn"],
            agent_id=event_payload["agent_id"],
            at=event_payload["at"],
            payload=event_payload["payload"],
        )
        event_hash = event_hash_for(event)
        chain_hash = chain_hash_for(previous, event_hash)
        exported.append(
            {
                "position": position,
                "event_group": event_group(event.event_type),
                "previous_chain_hash": previous,
                **event_payload,
                "event_hash": event_hash,
                "chain_hash": chain_hash,
            }
        )
        previous = chain_hash
    ledger = _read_ledger(root)
    ledger["events"] = exported
    ledger["canonical"]["event_count"] = len(exported)
    ledger["canonical"]["ledger_hash"] = previous
    _write_json(root / "ledger_export.json", ledger)


def _sync_ledger_evidence(root: Path) -> None:
    ledger = _read_ledger(root)
    bundle = _read_bundle(root)
    bundle["ledger_evidence"]["event_count"] = ledger["canonical"]["event_count"]
    bundle["ledger_evidence"]["ledger_hash"] = ledger["canonical"]["ledger_hash"]
    bundle["ledger_evidence"]["ledger_export_digest"] = file_sha256(root / "ledger_export.json")
    bundle["ledger_evidence"]["events"] = [_event_summary(event) for event in ledger["events"]]
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _sync_ledger_digest_only(root: Path) -> None:
    bundle = _read_bundle(root)
    bundle["ledger_evidence"]["ledger_export_digest"] = file_sha256(root / "ledger_export.json")
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _rewrite_manifest(root: Path) -> None:
    manifest = _read_json(root / "manifest.json")
    manifest["file_digests"] = {
        path: file_sha256(root / path)
        for path in ["outward_witness_bundle.json", "ledger_export.json", "artifacts/committed_output"]
        if (root / path).exists()
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    _write_json(root / "manifest.json", manifest)


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "position": event.get("position"),
        "sequence_index": event.get("position"),
        "event_hash": event.get("event_hash"),
        "previous_chain_hash": event.get("previous_chain_hash"),
        "chain_hash": event.get("chain_hash"),
    }


def _base_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in ("event_id", "event_type", "run_id", "turn", "agent_id", "at", "payload")}


def _remove_first(events: list[dict[str, Any]], event_type: str) -> None:
    events.pop(_index(events, event_type))


def _index(events: list[dict[str, Any]], event_type: str) -> int:
    for index, event in enumerate(events):
        if event.get("event_type") == event_type:
            return index
    raise ValueError(f"event not found: {event_type}")


def _read_bundle(root: Path) -> dict[str, Any]:
    return _read_json(root / "outward_witness_bundle.json")


def _read_ledger(root: Path) -> dict[str, Any]:
    return _read_json(root / "ledger_export.json")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create deterministic corruptions of an outward run witness package.")
    parser.add_argument("--base", required=True, help="Base witness package directory.")
    parser.add_argument("--corruption-id", required=True, help="ORP-CORR id to apply.")
    parser.add_argument("--output", required=True, help="Output corrupted package directory.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    result = corrupt_package(base=Path(args.base), output=Path(args.output), corruption_id=str(args.corruption_id))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"corruption_id={result['corruption_id']} result={result['result']}")
    return 0 if result.get("result") in {"created", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
