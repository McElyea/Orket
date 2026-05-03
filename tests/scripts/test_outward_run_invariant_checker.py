from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from orket.core.domain.outward_ledger import chain_hash_for, event_group, event_hash_for
from orket.core.domain.outward_run_events import LedgerEvent
from scripts.proof.outward_run_invariant_checker import evaluate_outward_run_invariants
from scripts.proof.outward_run_witness_contract import (
    COMPARE_SCOPE_DENIED,
    COMPARE_SCOPE_POLICY_REJECTED,
    compute_package_digest,
    file_sha256,
)
from scripts.proof.outward_run_witness_package import load_witness_package

_ARGS_DIGEST = "args-digest"
_MODEL_DIGESTS = {
    "model_invocation_digest": "model-invocation-digest",
    "model_prompt_redacted_digest": "prompt-digest",
    "model_response_redacted_digest": "response-digest",
    "proposal_extraction_digest": "extraction-digest",
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _valid_package(root: Path, *, run_id: str = "run-approved") -> Path:
    root.mkdir(parents=True)
    artifact = root / "artifacts" / "committed_output"
    artifact.parent.mkdir()
    artifact.write_bytes(b"model approved content")
    _write_ledger(root, _base_events(run_id))
    bundle = _bundle(run_id, ledger_digest=file_sha256(root / "ledger_export.json"), artifact_digest=file_sha256(artifact))
    _write_json(root / "outward_witness_bundle.json", bundle)
    _sync_ledger_evidence(root)
    return root


def _valid_denial_package(root: Path, *, run_id: str = "run-denied") -> Path:
    root.mkdir(parents=True)
    _write_ledger(root, _denial_events(run_id))
    artifact_digest = ""
    bundle = _bundle(run_id, ledger_digest=file_sha256(root / "ledger_export.json"), artifact_digest=artifact_digest)
    bundle["bundle_id"] = "bundle-denied"
    bundle["compare_scope"] = COMPARE_SCOPE_DENIED
    bundle["approval_authority"][0]["status"] = "denied"
    bundle["approval_authority"][0]["decided_at_iso"] = "2026-05-02T12:00:07+00:00"
    bundle["effect_evidence"] = []
    bundle["artifact_refs"] = []
    bundle["package_refs"] = {"ledger_export_path": "ledger_export.json"}
    _write_json(root / "outward_witness_bundle.json", bundle)
    _sync_ledger_evidence(root)
    return root


def _valid_policy_rejected_package(root: Path, *, run_id: str = "run-policy-rejected") -> Path:
    root.mkdir(parents=True)
    _write_ledger(root, _policy_rejected_events(run_id))
    bundle = _bundle(run_id, ledger_digest=file_sha256(root / "ledger_export.json"), artifact_digest="")
    bundle["bundle_id"] = "bundle-policy-rejected"
    bundle["compare_scope"] = COMPARE_SCOPE_POLICY_REJECTED
    bundle["approval_authority"] = []
    bundle["effect_evidence"] = []
    bundle["artifact_refs"] = []
    bundle["package_refs"] = {"ledger_export_path": "ledger_export.json"}
    bundle["policy_rejection_authority"] = [
        {
            "proposal_ref": _proposal_ref(run_id),
            "run_id": run_id,
            "turn_index": 1,
            "tool_name": "write_file",
            "tool_args_digest": _ARGS_DIGEST,
            "policy_result": "rejected",
            "reason": "path escaped workspace root",
            "event_position": 5,
            "policy_event_payload_digest": "policy-event-digest",
        }
    ]
    _write_json(root / "outward_witness_bundle.json", bundle)
    _sync_ledger_evidence(root)
    return root


def _base_events(run_id: str) -> list[dict[str, Any]]:
    proposal_id = f"proposal:{run_id}:write_file:0001"
    return [
        _event("run_submitted", run_id, 0, {"run_id": run_id, "status": "queued"}),
        _event("run_started", run_id, 0, {"run_id": run_id, "status": "running"}),
        _event("turn_started", run_id, 1, {"run_id": run_id, "turn": 1}),
        _event(
            "proposal_made",
            run_id,
            1,
            {
                "run_id": run_id,
                "tool": "write_file",
                "tool_name": "write_file",
                "tool_args_hash": _ARGS_DIGEST,
                "model_invocation_sha256": _MODEL_DIGESTS["model_invocation_digest"],
                "model_prompt_redacted_sha256": _MODEL_DIGESTS["model_prompt_redacted_digest"],
                "model_response_content_sha256": _MODEL_DIGESTS["model_response_redacted_digest"],
                "proposal_extraction_sha256": _MODEL_DIGESTS["proposal_extraction_digest"],
            },
        ),
        _event("proposal_pending_approval", run_id, 1, {"proposal_id": proposal_id, "tool_args_hash": _ARGS_DIGEST}),
        _event("proposal_approved", run_id, 1, {"proposal_id": proposal_id, "tool_args_hash": _ARGS_DIGEST}),
        _event("tool_invoked", run_id, 1, {"connector_name": "write_file", "args_hash": _ARGS_DIGEST, "outcome": "success"}),
        _event("commitment_recorded", run_id, 1, {"run_id": run_id, "tool": "write_file", "outcome": "success"}),
        _event("turn_completed", run_id, 1, {"run_id": run_id, "turn": 1, "outcome": "success"}),
        _event("run_completed", run_id, 1, {"run_id": run_id, "status": "completed", "outcome": "success"}),
    ]


def _denial_events(run_id: str) -> list[dict[str, Any]]:
    proposal_id = f"proposal:{run_id}:write_file:0001"
    return [
        _event("run_submitted", run_id, 0, {"run_id": run_id, "status": "queued"}),
        _event("run_started", run_id, 0, {"run_id": run_id, "status": "running"}),
        _event("turn_started", run_id, 1, {"run_id": run_id, "turn": 1}),
        _event(
            "proposal_made",
            run_id,
            1,
            {
                "run_id": run_id,
                "tool": "write_file",
                "tool_name": "write_file",
                "tool_args_hash": _ARGS_DIGEST,
                "model_invocation_sha256": _MODEL_DIGESTS["model_invocation_digest"],
                "model_prompt_redacted_sha256": _MODEL_DIGESTS["model_prompt_redacted_digest"],
                "model_response_content_sha256": _MODEL_DIGESTS["model_response_redacted_digest"],
                "proposal_extraction_sha256": _MODEL_DIGESTS["proposal_extraction_digest"],
            },
        ),
        _event("proposal_pending_approval", run_id, 1, {"proposal_id": proposal_id, "tool_args_hash": _ARGS_DIGEST}),
        _event("proposal_denied", run_id, 1, {"proposal_id": proposal_id, "tool_args_hash": _ARGS_DIGEST, "status": "denied"}),
        _event("turn_completed", run_id, 1, {"run_id": run_id, "turn": 1, "outcome": "denied"}),
        _event("run_completed", run_id, 1, {"run_id": run_id, "status": "completed", "outcome": "denied"}),
    ]


def _policy_rejected_events(run_id: str) -> list[dict[str, Any]]:
    return [
        _event("run_submitted", run_id, 0, {"run_id": run_id, "status": "queued"}),
        _event("run_started", run_id, 0, {"run_id": run_id, "status": "running"}),
        _event("turn_started", run_id, 1, {"run_id": run_id, "turn": 1}),
        _event(
            "proposal_made",
            run_id,
            1,
            {
                "run_id": run_id,
                "tool": "write_file",
                "tool_name": "write_file",
                "tool_args_hash": _ARGS_DIGEST,
                "proposal_ref": _proposal_ref(run_id),
                "model_invocation_sha256": _MODEL_DIGESTS["model_invocation_digest"],
                "model_prompt_redacted_sha256": _MODEL_DIGESTS["model_prompt_redacted_digest"],
                "model_response_content_sha256": _MODEL_DIGESTS["model_response_redacted_digest"],
                "proposal_extraction_sha256": _MODEL_DIGESTS["proposal_extraction_digest"],
            },
        ),
        _event(
            "proposal_policy_rejected",
            run_id,
            1,
            {
                "run_id": run_id,
                "turn": 1,
                "tool": "write_file",
                "tool_name": "write_file",
                "tool_args_hash": _ARGS_DIGEST,
                "proposal_ref": _proposal_ref(run_id),
                "policy_result": "rejected",
                "reason": "path escaped workspace root",
            },
        ),
        _event("turn_completed", run_id, 1, {"run_id": run_id, "turn": 1, "outcome": "policy_rejected"}),
        _event("run_completed", run_id, 1, {"run_id": run_id, "status": "completed", "outcome": "policy_rejected"}),
    ]


def _proposal_ref(run_id: str) -> str:
    return f"model_proposal:{run_id}:1:write_file:{_ARGS_DIGEST}"


def _event(event_type: str, run_id: str, turn: int, payload: dict[str, Any]) -> dict[str, Any]:
    index = _APPROVED_INDEX[event_type]
    return {
        "event_id": f"run:{run_id}:{index:04d}:{event_type}",
        "event_type": event_type,
        "run_id": run_id,
        "turn": turn,
        "agent_id": "outward-agent",
        "at": f"2026-05-02T12:00:{index:02d}+00:00",
        "payload": payload,
    }


_APPROVED_INDEX = {name: index for index, name in enumerate(
    [
        "run_submitted",
        "run_started",
        "turn_started",
        "proposal_made",
        "proposal_pending_approval",
        "proposal_approved",
        "tool_invoked",
        "commitment_recorded",
        "turn_completed",
        "run_completed",
        "proposal_denied",
        "proposal_policy_rejected",
    ],
    start=1,
)}


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
    _write_json(
        root / "ledger_export.json",
        {
            "schema_version": "ledger_export.v1",
            "export_scope": "all",
            "run_id": events[0]["run_id"],
            "types": ["all"],
            "canonical": {"event_count": len(exported), "ledger_hash": previous, "genesis": "GENESIS"},
            "events": exported,
            "omitted_spans": [],
            "verification": {"result": "valid"},
        },
    )


def _bundle(run_id: str, *, ledger_digest: str, artifact_digest: str) -> dict[str, Any]:
    return {
        "schema_version": "outward_run.witness_bundle.v1",
        "bundle_id": "bundle-approved",
        "run_id": run_id,
        "compare_scope": "outward_run_write_file_approved_v1",
        "operator_surface": "outward_run_witness_report.v1",
        "claim_tier_request": "outward_lab_only",
        "run_authority": {
            "run_id": run_id,
            "namespace": f"issue_{run_id}",
            "status": "completed",
            "run_status": "completed",
            "submitted_at_iso": "2026-05-02T12:00:00+00:00",
            "task_description": "Write approved file",
            "task_instruction": "Call write_file",
            "acceptance_contract_tool": "write_file",
            "acceptance_contract_sequence": None,
            "policy_overrides_digest": "policy-digest",
            "run_record_digest": "run-record-digest",
        },
        "approval_authority": [
            {
                "approval_id": f"proposal:{run_id}:write_file:0001",
                "run_id": run_id,
                "turn_index": 1,
                "tool_name": "write_file",
                "tool_args_digest": _ARGS_DIGEST,
                "status": "approved",
                "decided_at_iso": "2026-05-02T12:00:07+00:00",
                "approval_record_digest": "approval-record-digest",
            }
        ],
        "effect_evidence": [
            {
                "event_type": "tool_invoked",
                "run_id": run_id,
                "approval_id": f"proposal:{run_id}:write_file:0001",
                "turn_index": 1,
                "tool_name": "write_file",
                "tool_args_digest": _ARGS_DIGEST,
                "connector_result_digest": "connector-result-digest",
                "sequence_index": 1,
            }
        ],
        "model_invocation_evidence": [
            {
                "turn_index": 1,
                "model_provider": "fake-provider",
                "model_name": "fake-model",
                **_MODEL_DIGESTS,
            }
        ],
        "policy_identity": {
            "policy_overrides_digest": "policy-digest",
            "approval_required_tools": ["write_file"],
            "max_turns": 1,
            "approval_timeout_seconds": 30,
        },
        "ledger_evidence": {
            "ledger_export_schema": "ledger_export.v1",
            "run_id": run_id,
            "event_count": 10,
            "export_scope": "all",
            "ledger_hash": _ledger_hash(root_path=None),
            "events": [],
            "ledger_export_digest": ledger_digest,
            "ledger_export_package_path": "ledger_export.json",
        },
        "artifact_refs": [
            {
                "artifact_role": "committed_output",
                "path": "approved.txt",
                "package_path": "artifacts/committed_output",
                "digest": artifact_digest,
                "classification": "authority",
            }
        ],
        "package_refs": {
            "ledger_export_path": "ledger_export.json",
            "committed_output_path": "artifacts/committed_output",
        },
    }


def _sync_ledger_evidence(root: Path) -> None:
    bundle = _read_bundle(root)
    ledger = json.loads((root / "ledger_export.json").read_text(encoding="utf-8"))
    bundle["ledger_evidence"]["event_count"] = ledger["canonical"]["event_count"]
    bundle["ledger_evidence"]["ledger_hash"] = ledger["canonical"]["ledger_hash"]
    bundle["ledger_evidence"]["export_scope"] = ledger["export_scope"]
    bundle["ledger_evidence"]["events"] = [
        {
            "event_type": event["event_type"],
            "position": event["position"],
            "sequence_index": event["position"],
            "event_hash": event["event_hash"],
            "previous_chain_hash": event["previous_chain_hash"],
            "chain_hash": event["chain_hash"],
            "event_payload_digest": hashlib.sha256(
                json.dumps(event["payload"], sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        for event in ledger["events"]
    ]
    bundle["ledger_evidence"]["ledger_export_digest"] = file_sha256(root / "ledger_export.json")
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _ledger_hash(root_path: Path | None) -> str:
    return "" if root_path is None else json.loads((root_path / "ledger_export.json").read_text(encoding="utf-8"))["canonical"]["ledger_hash"]


def _rewrite_manifest(root: Path) -> None:
    existing = json.loads((root / "manifest.json").read_text(encoding="utf-8")) if (root / "manifest.json").exists() else {}
    bundle = _read_bundle(root) if (root / "outward_witness_bundle.json").exists() else {}
    artifact_paths = {"committed_output": "artifacts/committed_output"} if (root / "artifacts" / "committed_output").exists() else {}
    manifest = {
        "schema_version": "outward_run_witness_package.v1",
        "package_id": str(existing.get("package_id") or "package-approved"),
        "compare_scope": str(existing.get("compare_scope") or bundle.get("compare_scope") or "outward_run_write_file_approved_v1"),
        "bundle_path": "outward_witness_bundle.json",
        "ledger_export_path": "ledger_export.json",
        "artifact_paths": artifact_paths,
        "file_digests": {
            path: file_sha256(root / path)
            for path in ["outward_witness_bundle.json", "ledger_export.json", "artifacts/committed_output"]
            if (root / path).exists()
        },
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    _write_json(root / "manifest.json", manifest)


def _read_bundle(root: Path) -> dict[str, Any]:
    return json.loads((root / "outward_witness_bundle.json").read_text(encoding="utf-8"))


def _load_model(root: Path, *, scope: str = "outward_run_write_file_approved_v1") -> dict[str, Any]:
    loaded = load_witness_package(root)
    assert loaded.package is not None
    return evaluate_outward_run_invariants(loaded.package, scope=scope)


def _mutate_bundle(root: Path, mutator) -> None:
    bundle = _read_bundle(root)
    mutator(bundle)
    _write_json(root / "outward_witness_bundle.json", bundle)
    _rewrite_manifest(root)


def _mutate_events(root: Path, mutator) -> None:
    ledger = json.loads((root / "ledger_export.json").read_text(encoding="utf-8"))
    events = [{key: event[key] for key in ("event_id", "event_type", "run_id", "turn", "agent_id", "at", "payload")} for event in ledger["events"]]
    mutator(events)
    _write_ledger(root, events)
    _sync_ledger_evidence(root)


def _assert_failure(tmp_path: Path, code: str, mutator) -> None:
    root = _valid_package(tmp_path / "outward_run_witness_package.v1")
    mutator(root)
    model = _load_model(root)
    assert model["result"] == "fail"
    assert code in model["failures"]


def test_valid_approved_package_passes_all_single_turn_invariants(tmp_path: Path) -> None:
    """Layer: contract. Verifies a full approved package satisfies the mechanized single-turn model."""
    root = _valid_package(tmp_path / "outward_run_witness_package.v1")
    _sync_ledger_evidence(root)

    model = _load_model(root)

    assert model["result"] == "pass"
    assert model["claim_tier_assigned"] == "outward_lab_only"
    assert all(item["status"] == "passed" for item in model["invariants"])


def test_valid_denial_package_passes_denial_invariants(tmp_path: Path) -> None:
    """Layer: unit. Verifies a denial package proves no effect or commitment after denial."""
    root = _valid_denial_package(tmp_path / "outward_run_witness_package.v1")

    model = _load_model(root, scope=COMPARE_SCOPE_DENIED)

    assert model["result"] == "pass"
    assert model["claim_tier_assigned"] == "outward_lab_only"
    assert all(item["status"] == "passed" for item in model["invariants"])


def test_valid_policy_rejected_package_passes_policy_invariants(tmp_path: Path) -> None:
    """Layer: unit. Verifies a policy-rejected package proves no approval, effect, or commitment."""
    root = _valid_policy_rejected_package(tmp_path / "outward_run_witness_package.v1")

    model = _load_model(root, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert model["result"] == "pass"
    assert model["claim_tier_assigned"] == "outward_lab_only"
    assert all(item["status"] == "passed" for item in model["invariants"])


def test_denial_package_missing_denial_event_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies denial scope requires a proposal_denied event before terminal truth."""
    root = _valid_denial_package(tmp_path / "outward_run_witness_package.v1")
    _mutate_events(root, lambda events: events.pop(5))

    model = _load_model(root, scope=COMPARE_SCOPE_DENIED)

    assert model["result"] == "fail"
    assert "denial_event_missing" in model["failures"]


def test_denial_package_missing_approval_authority_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies denial scope requires approval authority, not only ledger events."""
    root = _valid_denial_package(tmp_path / "outward_run_witness_package.v1")
    _mutate_bundle(root, lambda bundle: bundle.update({"approval_authority": []}))

    model = _load_model(root, scope=COMPARE_SCOPE_DENIED)

    assert model["result"] == "fail"
    assert "approval_authority_missing" in model["failures"]


def test_policy_rejected_package_missing_policy_event_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies policy-rejection scope requires proposal_policy_rejected before terminal truth."""
    root = _valid_policy_rejected_package(tmp_path / "outward_run_witness_package.v1")
    _mutate_events(root, lambda events: events.pop(4))

    model = _load_model(root, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert model["result"] == "fail"
    assert "policy_rejection_event_missing" in model["failures"]


def test_denial_package_tool_invocation_after_denial_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies a denied proposal cannot be followed by a tool invocation."""
    root = _valid_denial_package(tmp_path / "outward_run_witness_package.v1")
    run_id = "run-denied"
    _mutate_events(
        root,
        lambda events: events.insert(6, _event("tool_invoked", run_id, 1, {"connector_name": "write_file", "args_hash": _ARGS_DIGEST})),
    )

    model = _load_model(root, scope=COMPARE_SCOPE_DENIED)

    assert model["result"] == "fail"
    assert "denied_proposal_invoked" in model["failures"]


def test_policy_rejected_package_tool_invocation_after_rejection_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies a policy-rejected proposal cannot be followed by tool invocation."""
    root = _valid_policy_rejected_package(tmp_path / "outward_run_witness_package.v1")
    run_id = "run-policy-rejected"
    _mutate_events(
        root,
        lambda events: events.insert(
            5,
            _event("tool_invoked", run_id, 1, {"connector_name": "write_file", "args_hash": _ARGS_DIGEST}),
        ),
    )

    model = _load_model(root, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert model["result"] == "fail"
    assert "policy_rejected_proposal_invoked" in model["failures"]


def test_policy_rejected_package_commitment_after_rejection_rejects(tmp_path: Path) -> None:
    """Layer: unit. Verifies a policy-rejected proposal cannot be followed by a commitment."""
    root = _valid_policy_rejected_package(tmp_path / "outward_run_witness_package.v1")
    run_id = "run-policy-rejected"
    _mutate_events(
        root,
        lambda events: events.insert(
            5,
            _event("commitment_recorded", run_id, 1, {"run_id": run_id, "tool": "write_file", "outcome": "policy_rejected"}),
        ),
    )

    model = _load_model(root, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert model["result"] == "fail"
    assert "policy_rejected_proposal_committed" in model["failures"]


def test_equivalent_successful_packages_have_stable_invariant_signature(tmp_path: Path) -> None:
    """Layer: contract. Verifies invariant signatures exclude generated ids and paths."""
    first = _valid_package(tmp_path / "one" / "outward_run_witness_package.v1", run_id="run-one")
    second = _valid_package(tmp_path / "two" / "outward_run_witness_package.v1", run_id="run-two")
    _sync_ledger_evidence(first)
    _sync_ledger_evidence(second)

    assert _load_model(first)["invariant_signature"] == _load_model(second)["invariant_signature"]


@pytest.mark.parametrize(
    ("code", "mutator"),
    [
        ("effect_before_admission", lambda root: _mutate_events(root, lambda events: events.pop(0))),
        ("effect_before_approval", lambda root: _mutate_events(root, lambda events: events.pop(5))),
        ("terminal_status_drift", lambda root: _mutate_bundle(root, lambda bundle: bundle["run_authority"].update({"status": "failed"}))),
        ("effect_evidence_missing", lambda root: _mutate_bundle(root, lambda bundle: bundle.update({"effect_evidence": []}))),
        ("missing_authority_digest", lambda root: _mutate_bundle(root, lambda bundle: bundle["run_authority"].pop("run_record_digest"))),
        ("full_ledger_export_required", lambda root: _make_partial_export(root)),
        ("claim_tier_not_supported", lambda root: _mutate_bundle(root, lambda bundle: bundle.update({"claim_tier_request": "outward_verifier_stable"}))),
        ("proposal_ordering_violated", lambda root: _mutate_events(root, lambda events: events.insert(3, events.pop(4)))),
        ("tool_args_digest_drift", lambda root: _mutate_bundle(root, lambda bundle: bundle["effect_evidence"][0].update({"tool_args_digest": "drift"}))),
        ("commitment_missing_after_effect", lambda root: _mutate_events(root, lambda events: events.pop(7))),
        ("turn_not_completed_after_commitment", lambda root: _mutate_events(root, lambda events: events.pop(8))),
        ("model_invocation_digest_drift", lambda root: _mutate_bundle(root, lambda bundle: bundle["model_invocation_evidence"][0].update({"model_invocation_digest": "drift"}))),
        ("denied_proposal_invoked", lambda root: _mutate_events(root, lambda events: events.insert(6, _event("proposal_denied", events[0]["run_id"], 1, {"proposal_id": "denied"})))),
        ("policy_rejected_proposal_invoked", lambda root: _mutate_events(root, lambda events: events.insert(6, _event("proposal_policy_rejected", events[0]["run_id"], 1, {"proposal_id": "policy"})))),
        ("ledger_sequence_gap", lambda root: _duplicate_ledger_position(root)),
    ],
)
def test_single_turn_invariants_fail_closed_with_stable_codes(tmp_path: Path, code: str, mutator) -> None:
    """Layer: contract. Verifies focused corruptions produce stable invariant failure codes."""
    _assert_failure(tmp_path, code, mutator)


def _make_partial_export(root: Path) -> None:
    ledger = json.loads((root / "ledger_export.json").read_text(encoding="utf-8"))
    ledger["export_scope"] = "partial_view"
    ledger["verification"] = {"result": "partial_valid"}
    _write_json(root / "ledger_export.json", ledger)
    _sync_ledger_evidence(root)


def _duplicate_ledger_position(root: Path) -> None:
    ledger = json.loads((root / "ledger_export.json").read_text(encoding="utf-8"))
    ledger["events"][1]["position"] = 1
    _write_json(root / "ledger_export.json", ledger)
    _sync_ledger_evidence(root)
