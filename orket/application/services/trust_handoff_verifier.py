from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.core.domain.outward_ledger import verify_ledger_export

from orket.application.services.trust_handoff_contract import (
    ADMITTED_SOURCE_WITNESS_SCOPES,
    BUNDLE_SCHEMA_VERSION,
    COMMITTED_OUTPUT_PATH,
    COMPARE_SCOPE,
    COMPATIBILITY_SCOPE_PATH,
    KEY_AUTHORITY_NOTE,
    LEDGER_EXPORT_PATH,
    PACKAGE_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    SCOPE_SCHEMA_VERSION,
    SOURCE_WITNESS_BUNDLE_PATH,
    BUNDLE_PATH,
    canonical_json_digest,
    envelope_digest,
    failure_class,
    load_json_bytes,
    package_digest,
    scope_digest,
    sha256_bytes,
    stable_invariant_signature,
)

_REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "package_id",
    "source_run_id",
    "target_agent_id",
    "bundle_path",
    "ledger_export_path",
    "source_witness_bundle_path",
    "compatibility_scope_path",
    "artifact_paths",
    "package_digest",
    "issued_at_iso",
}
_REQUIRED_BUNDLE_FIELDS = {
    "schema_version",
    "bundle_id",
    "source_run_id",
    "source_agent_id",
    "target_agent_id",
    "handoff_policy_compatibility_scope_id",
    "committed_output_digest",
    "source_policy_digest",
    "source_policy_identity",
    "approval_record_digest",
    "commitment_record_digest",
    "ledger_export_digest",
    "source_witness_bundle_digest",
    "ledger_event_count",
    "compare_scope",
    "envelope_digest",
}


@dataclass(frozen=True)
class TrustHandoffVerificationContext:
    expected_scope_id: str | None = None
    expected_source_agent_id: str | None = None
    expected_target_agent_id: str | None = None


@dataclass(frozen=True)
class _LoadedPackage:
    root: Path
    manifest: dict[str, Any]
    files: dict[str, bytes]


@dataclass
class _State:
    checks: list[dict[str, Any]] = field(default_factory=list)
    bundle: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    output_anchor: dict[str, Any] = field(default_factory=dict)
    policy_anchor: dict[str, Any] = field(default_factory=dict)
    policy_compatibility: dict[str, Any] = field(default_factory=dict)

    def check(self, check_id: str, passed: bool, reason: str, detail: str | None = None) -> None:
        self.checks.append({"check_id": check_id, "passed": passed, "detail": detail})
        if not passed:
            raise _VerificationFailure(reason, detail)


class _VerificationFailure(Exception):
    def __init__(self, reason: str, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def verify_trust_handoff_package(
    package_path: Path,
    *,
    context: TrustHandoffVerificationContext | None = None,
) -> dict[str, Any]:
    state = _State()
    context = context or TrustHandoffVerificationContext()
    try:
        loaded = _load_package(package_path, state)
        _verify_loaded_package(loaded, state, context)
        return _report(state, None, None)
    except _VerificationFailure as exc:
        return _report(state, exc.reason, exc.detail)


def _load_package(package_path: Path, state: _State) -> _LoadedPackage:
    root = package_path.resolve()
    manifest_path = root / "manifest.json"
    state.check("MATH-CHECK-001", manifest_path.exists(), "package_manifest_missing")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = load_json_bytes(manifest_bytes)
    except (OSError, UnicodeDecodeError, ValueError):
        state.check("MATH-CHECK-001", False, "package_manifest_schema_invalid", "parse")
    state.manifest = manifest
    schema_ok = manifest.get("schema_version") == PACKAGE_SCHEMA_VERSION and _REQUIRED_MANIFEST_FIELDS <= set(manifest)
    artifact_paths = manifest.get("artifact_paths")
    schema_ok = schema_ok and isinstance(artifact_paths, dict) and bool(artifact_paths.get("committed_output"))
    state.check("MATH-CHECK-001", bool(schema_ok), "package_manifest_schema_invalid")

    refs = _manifest_refs(manifest)
    resolved: dict[str, Path] = {}
    for role, ref in refs.items():
        path = _resolve_package_ref(root, ref)
        state.check("MATH-CHECK-002", path is not None, "package_ref_outside_package", role)
        resolved[role] = path
    for role, path in resolved.items():
        state.check("MATH-CHECK-002", path.exists(), _missing_code(role), role)

    declared = {path.relative_to(root).as_posix() for path in resolved.values()}
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    allowed = declared | {"manifest.json"}
    state.check("MATH-CHECK-003", actual <= allowed, "unexpected_package_file")

    files = {rel: (root / rel).read_bytes() for rel in sorted(declared)}
    state.check(
        "MATH-CHECK-004",
        manifest.get("package_digest") == package_digest(files),
        "package_digest_mismatch",
    )
    return _LoadedPackage(root=root, manifest=manifest, files=files)


def _verify_loaded_package(
    loaded: _LoadedPackage,
    state: _State,
    context: TrustHandoffVerificationContext,
) -> None:
    manifest = loaded.manifest
    bundle = _json_file(loaded, str(manifest["bundle_path"]), "bundle_schema_invalid")
    state.bundle = bundle
    schema_ok = bundle.get("schema_version") == BUNDLE_SCHEMA_VERSION and _REQUIRED_BUNDLE_FIELDS <= set(bundle)
    schema_ok = schema_ok and isinstance(bundle.get("source_policy_identity"), dict)
    state.check("MATH-CHECK-005", bool(schema_ok), "bundle_schema_invalid")
    state.check("MATH-CHECK-006", bundle.get("compare_scope") == COMPARE_SCOPE, "bundle_schema_invalid", "compare_scope")
    state.check("MATH-CHECK-007", bundle.get("envelope_digest") == envelope_digest(bundle), "envelope_digest_mismatch")

    ledger_rel = str(manifest["ledger_export_path"])
    ledger_bytes = loaded.files[ledger_rel]
    state.check("MATH-CHECK-008", bundle.get("ledger_export_digest") == sha256_bytes(ledger_bytes), "ledger_export_digest_mismatch")
    ledger = _json_file(loaded, ledger_rel, "ledger_export_partial_view")
    state.check("MATH-CHECK-009", ledger.get("export_scope") == "all", "ledger_export_partial_view")
    state.check("MATH-CHECK-009", verify_ledger_export(ledger).get("result") == "valid", "ledger_export_partial_view")
    event_count = len([event for event in ledger.get("events") or [] if isinstance(event, dict)])
    state.check("MATH-CHECK-010", int(bundle.get("ledger_event_count") or -1) == event_count, "ledger_event_count_mismatch")

    witness_rel = str(manifest["source_witness_bundle_path"])
    witness_bytes = loaded.files[witness_rel]
    state.check(
        "MATH-CHECK-011",
        bundle.get("source_witness_bundle_digest") == sha256_bytes(witness_bytes),
        "source_witness_bundle_digest_mismatch",
    )
    witness = _json_file(loaded, witness_rel, "source_witness_bundle_invalid")
    _check_witness_alignment(state, witness, bundle)
    events = [event for event in ledger.get("events") or [] if isinstance(event, dict)]
    approval = _first_event(events, "proposal_approved")
    commitment = _first_event(events, "commitment_recorded")
    state.check("MATH-CHECK-013", _payload_digest(approval) == bundle.get("approval_record_digest"), "approval_record_missing_or_drifted")
    state.check(
        "MATH-CHECK-014",
        _payload_digest(commitment) == bundle.get("commitment_record_digest"),
        "commitment_record_missing_or_drifted",
    )
    state.check(
        "MATH-CHECK-015",
        _position(approval) < _position(commitment),
        "approval_before_commitment_ordering_violated",
    )
    state.check("MATH-CHECK-016", not _post_approval_denial(events, approval), "post_approval_denial_present")

    artifact_bytes = loaded.files[str(manifest["artifact_paths"]["committed_output"])]
    actual_output_digest = sha256_bytes(artifact_bytes)
    state.check("MATH-CHECK-017", actual_output_digest == bundle.get("committed_output_digest"), "committed_output_digest_mismatch")
    _check_source_output_anchor(state, witness, commitment, bundle)
    _check_source_policy_anchor(state, witness, bundle)
    scope = _json_file(loaded, str(manifest["compatibility_scope_path"]), "compatibility_scope_schema_invalid")
    _check_scope_and_identity(state, scope, bundle, manifest, ledger, context)


def _check_witness_alignment(state: _State, witness: dict[str, Any], bundle: dict[str, Any]) -> None:
    ledger = witness.get("ledger_evidence") if isinstance(witness.get("ledger_evidence"), dict) else {}
    valid_ref = _committed_artifact_ref(witness) is not None
    passed = (
        witness.get("schema_version") == "outward_run.witness_bundle.v1"
        and witness.get("run_id") == bundle.get("source_run_id")
        and witness.get("compare_scope") in ADMITTED_SOURCE_WITNESS_SCOPES
        and ledger.get("ledger_export_digest") == bundle.get("ledger_export_digest")
        and valid_ref
    )
    state.check("MATH-CHECK-012", passed, "source_witness_bundle_invalid")


def _check_source_output_anchor(
    state: _State,
    witness: dict[str, Any],
    commitment: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    digest = str(bundle.get("committed_output_digest") or "")
    payload = commitment.get("payload") if isinstance(commitment.get("payload"), dict) else {}
    path1 = payload.get("committed_output_digest") == digest
    ref = _committed_artifact_ref(witness)
    path2 = bool(ref and ref.get("digest") == digest and ref.get("package_path") == COMMITTED_OUTPUT_PATH)
    anchor_path = "commitment_recorded.payload.committed_output_digest" if path1 else "source_outward_witness_bundle.artifact_refs"
    state.output_anchor = {"anchor_path": anchor_path if path1 or path2 else None, "committed_output_digest": digest, "anchored": path1 or path2}
    state.check("MATH-CHECK-018", path1 or path2, "committed_output_not_ledger_anchored")


def _check_source_policy_anchor(state: _State, witness: dict[str, Any], bundle: dict[str, Any]) -> None:
    run_authority = witness.get("run_authority") if isinstance(witness.get("run_authority"), dict) else {}
    anchored = run_authority.get("policy_overrides_digest") == bundle.get("source_policy_digest")
    state.policy_anchor = {
        "source_policy_digest": bundle.get("source_policy_digest"),
        "anchored": anchored,
        "source": "source_outward_witness_bundle.run_authority.policy_overrides_digest",
    }
    state.check("MATH-CHECK-019", anchored, "source_policy_digest_not_ledger_anchored")


def _check_scope_and_identity(
    state: _State,
    scope: dict[str, Any],
    bundle: dict[str, Any],
    manifest: dict[str, Any],
    ledger: dict[str, Any],
    context: TrustHandoffVerificationContext,
) -> None:
    schema_ok = scope.get("schema_version") == SCOPE_SCHEMA_VERSION and isinstance(scope.get("admitted_source_policy_digests"), list)
    schema_ok = schema_ok and isinstance(scope.get("admitted_source_agent_ids"), list)
    state.check("MATH-CHECK-020", bool(schema_ok), "compatibility_scope_schema_invalid")
    state.check("MATH-CHECK-020", scope.get("scope_digest") == scope_digest(scope), "compatibility_scope_digest_mismatch")
    scope_matches = scope.get("scope_id") == bundle.get("handoff_policy_compatibility_scope_id")
    if context.expected_scope_id is not None:
        scope_matches = scope_matches and scope.get("scope_id") == context.expected_scope_id
    state.check("MATH-CHECK-020", scope_matches, "compatibility_scope_schema_invalid", "scope_id")
    digest = bundle.get("source_policy_digest")
    policy_ok = digest in {str(item) for item in scope.get("admitted_source_policy_digests") or []}
    state.policy_compatibility = {"scope_id": scope.get("scope_id"), "source_policy_digest": digest, "compatible": policy_ok}
    state.check("MATH-CHECK-021", policy_ok, "trust_handoff_policy_incompatible")
    admitted_agents = [str(item) for item in scope.get("admitted_source_agent_ids") or []]
    agent_ok = not admitted_agents or bundle.get("source_agent_id") in admitted_agents
    if context.expected_source_agent_id is not None:
        agent_ok = agent_ok and bundle.get("source_agent_id") == context.expected_source_agent_id
    state.check("MATH-CHECK-022", agent_ok, "trust_handoff_agent_not_admitted")
    identity = bundle.get("source_policy_identity") if isinstance(bundle.get("source_policy_identity"), dict) else {}
    state.check("MATH-CHECK-023", identity.get("policy_digest") == digest, "policy_identity_digest_mismatch")
    target_ok = bundle.get("target_agent_id") == manifest.get("target_agent_id")
    if context.expected_target_agent_id is not None:
        target_ok = target_ok and bundle.get("target_agent_id") == context.expected_target_agent_id
    state.check("MATH-CHECK-024", target_ok, "target_agent_id_mismatch")
    source_ok = bundle.get("source_run_id") == manifest.get("source_run_id") == ledger.get("run_id")
    state.check("MATH-CHECK-025", source_ok, "source_run_id_drift")


def _manifest_refs(manifest: dict[str, Any]) -> dict[str, str]:
    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    refs = {
        "bundle": str(manifest.get("bundle_path") or BUNDLE_PATH),
        "ledger": str(manifest.get("ledger_export_path") or LEDGER_EXPORT_PATH),
        "source_witness": str(manifest.get("source_witness_bundle_path") or SOURCE_WITNESS_BUNDLE_PATH),
        "compatibility_scope": str(manifest.get("compatibility_scope_path") or COMPATIBILITY_SCOPE_PATH),
        "committed_output": str(artifact_paths.get("committed_output") or COMMITTED_OUTPUT_PATH),
    }
    supplement = manifest.get("supplementary_paths") if isinstance(manifest.get("supplementary_paths"), list) else []
    refs.update({f"supplementary:{index}": str(path) for index, path in enumerate(supplement)})
    return refs


def _resolve_package_ref(root: Path, ref: str) -> Path | None:
    clean = str(ref or "").strip()
    if not clean:
        return None
    resolved = (root / clean).resolve()
    return resolved if resolved.is_relative_to(root) else None


def _missing_code(role: str) -> str:
    return {
        "bundle": "bundle_missing",
        "ledger": "ledger_export_missing",
        "source_witness": "source_witness_bundle_missing",
        "compatibility_scope": "compatibility_scope_missing",
        "committed_output": "committed_output_missing",
    }.get(role, "package_manifest_schema_invalid")


def _json_file(loaded: _LoadedPackage, rel: str, failure_code: str) -> dict[str, Any]:
    try:
        return load_json_bytes(loaded.files[rel])
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        raise _VerificationFailure(failure_code, "parse") from exc


def _first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for event in events:
        if event.get("event_type") == event_type:
            return event
    return {}


def _payload_digest(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else None
    return canonical_json_digest(payload) if payload is not None else ""


def _position(event: dict[str, Any]) -> int:
    return int(event.get("position") or 0)


def _post_approval_denial(events: list[dict[str, Any]], approval: dict[str, Any]) -> bool:
    approval_position = _position(approval)
    for event in events:
        if _position(event) > approval_position and event.get("event_type") in {"proposal_denied", "proposal_policy_rejected"}:
            return True
    return False


def _committed_artifact_ref(witness: dict[str, Any]) -> dict[str, Any] | None:
    refs = [item for item in witness.get("artifact_refs") or [] if isinstance(item, dict)]
    matching = [
        ref
        for ref in refs
        if ref.get("artifact_role") == "committed_output" and ref.get("classification") == "authority" and ref.get("package_path")
    ]
    return matching[0] if len(matching) == 1 and matching[0].get("digest") else None


def _report(state: _State, reason: str | None, detail: str | None) -> dict[str, Any]:
    bundle = state.bundle
    manifest = state.manifest
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "bundle_id": bundle.get("bundle_id"),
        "source_run_id": bundle.get("source_run_id") or manifest.get("source_run_id"),
        "source_agent_id": bundle.get("source_agent_id"),
        "target_agent_id": bundle.get("target_agent_id") or manifest.get("target_agent_id"),
        "compare_scope": bundle.get("compare_scope") or COMPARE_SCOPE,
        "envelope_digest": bundle.get("envelope_digest"),
        "result": "accepted" if reason is None else "rejected",
        "rejection_reason": reason,
        "rejection_class": failure_class(reason),
        "checks_performed": state.checks,
        "key_authority_note": KEY_AUTHORITY_NOTE,
        "source_output_anchor_result": state.output_anchor,
        "source_policy_anchor_result": state.policy_anchor,
        "policy_compatibility_result": state.policy_compatibility,
        "failure_detail": detail,
        "invariant_signature": stable_invariant_signature(state.checks, reason),
    }
