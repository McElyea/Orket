# Slice 02 - Outward Run Witness Bundle

Last updated: 2026-05-01
Status: Archived slice plan - package contract promoted for approved single-turn boundary
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`

## Purpose

Extend the trusted-run witness approach to the outward-facing run pipeline.

The bundle must let an offline verifier check outward-run proposal, admission, approval, effect, final-truth, ledger, and claim evidence without consulting mutable runtime state.

## Scope

In scope:
1. outward run records
2. approval records
3. connector invocation evidence
4. run event ledger and export evidence
5. final truth or terminal result evidence
6. policy and configuration identity needed by the claim
7. model invocation evidence digests

Out of scope:
1. provider output semantic correctness
2. live database reads during verification
3. model or provider calls during verification
4. public trust-boundary widening by bundle existence alone

## Package Contract Draft - `outward_run_witness_package.v1`

This draft governs what the package producer must emit and what the offline verifier must consume for independent proof. It must be extracted to `docs/specs/OUTWARD_RUN_WITNESS_V1.md` before implementation code treats it as authority.

The proof object is a package, not a mutable workspace pointer:

```text
outward_run_witness_package.v1/
  manifest.json
  outward_witness_bundle.json
  ledger_export.json
  artifacts/
    committed_output
```

Bundle-only verification may validate schema and internal commitments, but it cannot prove full ledger integrity, absence of omitted events, or committed artifact bytes. Full proof claims consume the package. A bundle-only mode must not return `accepted` for proof claims.

### Package Manifest

`manifest.json` carries:

```json
{
  "schema_version": "outward_run_witness_package.v1",
  "package_id": "<uuid>",
  "compare_scope": "outward_run_write_file_approved_v1",
  "bundle_path": "outward_witness_bundle.json",
  "ledger_export_path": "ledger_export.json",
  "artifact_paths": {
    "committed_output": "artifacts/committed_output"
  },
  "package_digest": "<sha256 hex over canonical manifest entries and file digests>"
}
```

The verifier recomputes file digests from package bytes. A manifest digest that cannot be recomputed is a blocker.

## Bundle Contract Draft - `outward_run.witness_bundle.v1`

### Top-Level Schema

```json
{
  "schema_version": "outward_run.witness_bundle.v1",
  "bundle_id": "<uuid>",
  "run_id": "<string>",
  "produced_at_iso": "<utc-iso8601 metadata only>",
  "compare_scope": "<admitted scope>",
  "operator_surface": "outward_run_witness_report.v1",
  "claim_tier_request": "<lane-local outward claim posture>",
  "run_authority": {},
  "approval_authority": [],
  "ledger_evidence": {},
  "effect_evidence": [],
  "model_invocation_evidence": [],
  "policy_identity": {},
  "artifact_refs": [],
  "package_refs": {
    "ledger_export_path": "ledger_export.json",
    "committed_output_path": "artifacts/committed_output"
  }
}
```

### `run_authority`

Required fields:

```json
{
  "run_id": "<string>",
  "namespace": "<string>",
  "status": "<terminal status for success claim>",
  "run_status": "<terminal ledger status>",
  "submitted_at_iso": "<metadata>",
  "task_description": "<string>",
  "task_instruction": "<string>",
  "acceptance_contract_tool": "<governed tool name or null>",
  "acceptance_contract_sequence": "<list<string> or null>",
  "policy_overrides_digest": "<sha256 hex of canonical policy_overrides bytes or empty-string>",
  "run_record_digest": "<sha256 hex of canonical run record bytes>"
}
```

Classification: authority.

### `approval_authority`

One entry per approval proposal. Required fields per entry:

```json
{
  "approval_id": "<string>",
  "run_id": "<string>",
  "turn_index": 0,
  "tool_name": "<string>",
  "tool_args_digest": "<sha256 hex of canonical tool_args bytes>",
  "status": "approved",
  "decided_at_iso": "<metadata>",
  "approval_record_digest": "<sha256 hex of canonical approval record bytes>"
}
```

Allowed `status` values are `approved`, `denied`, `expired`, and `policy_rejected`.

Classification: authority.

### `ledger_evidence`

Required fields:

```json
{
  "ledger_export_schema": "ledger_export.v1",
  "run_id": "<string>",
  "event_count": 0,
  "export_scope": "all",
  "ledger_hash": "<canonical ledger_export.v1 ledger_hash>",
  "events": [
    {
      "event_type": "<string>",
      "position": 1,
      "sequence_index": 0,
      "event_hash": "<sha256 hex>",
      "previous_chain_hash": "GENESIS",
      "chain_hash": "<sha256 hex>",
      "event_payload_digest": "<sha256 hex>"
    }
  ],
  "ledger_export_digest": "<sha256 hex of full ledger_export.v1 bytes>",
  "ledger_export_package_path": "ledger_export.json"
}
```

Classification: authority only when the package includes the full `ledger_export.v1` JSON bytes at `ledger_export_package_path` and the verifier recomputes hashes using `docs/specs/LEDGER_EXPORT_V1.md`.

If the package includes only event hashes, chain hashes, or payload digests, the verifier may treat those values as commitments, but it must not accept claims that require independent ledger verification, event absence, or full-ledger completeness.

### `effect_evidence`

One entry per `tool_invoked` event. Required fields per entry:

```json
{
  "event_type": "tool_invoked",
  "run_id": "<string>",
  "approval_id": "<string>",
  "turn_index": 0,
  "tool_name": "<string>",
  "tool_args_digest": "<sha256 hex>",
  "connector_result_digest": "<sha256 hex of canonical connector result bytes>",
  "sequence_index": 0
}
```

Classification: authority.

For `outward_run_write_file_approved_v1`, the canonical approved event sequence is:

```text
run_submitted
run_started
turn_started
proposal_made
proposal_pending_approval
proposal_approved
tool_invoked
commitment_recorded
turn_completed
run_completed
```

### `model_invocation_evidence`

One entry per model call. Required fields per entry:

```json
{
  "turn_index": 0,
  "model_provider": "<string>",
  "model_name": "<string>",
  "model_invocation_digest": "<sha256 hex of model_invocation.json bytes>",
  "model_prompt_redacted_digest": "<sha256 hex>",
  "model_response_redacted_digest": "<sha256 hex>",
  "proposal_extraction_digest": "<sha256 hex>"
}
```

Classification: derived. The digests are authority-bearing only when anchored by the ledger event payload or source authority refs. The redacted JSON files remain support-only at verification time unless a later contract promotes them.

For ORP-INV-012, model evidence is anchored only if the packaged full ledger export contains the `proposal_made` payload fields naming the model invocation, prompt, response, and proposal-extraction digests, and those digests match the bundle's `model_invocation_evidence` entry.

This proves only that the proposal was recorded with anchored model-evidence digests. It does not prove provider output semantics, replay the model call, or validate that the model reasoned correctly.

### `policy_identity`

Required fields:

```json
{
  "policy_overrides_digest": "<sha256 hex>",
  "approval_required_tools": ["<string>"],
  "max_turns": 1,
  "approval_timeout_seconds": 300
}
```

Classification: authority. The verifier uses this to check that the governed tool was approval-required at submission time.

### `artifact_refs`

One entry per verifiable artifact. Required fields per entry:

```json
{
  "artifact_role": "committed_output",
  "path": "<workspace-relative path>",
  "digest": "<sha256 hex>",
  "classification": "authority"
}
```

For `outward_run_write_file_approved_v1`, the `committed_output` artifact is the file written by the connector after approval. Its digest is authority only when the package includes the artifact bytes and the validator recomputes the digest from `artifacts/committed_output`.

## Source Authority Ref and Digest Rules

1. Digest-only evidence is a commitment, not authority by itself.
2. Any digest used as authority must be recomputed from canonical bytes included in the witness package, or be anchored by a verified `ledger_export.v1` payload field from the full package ledger export.
3. Digest values are lowercase SHA-256 hex over canonical serialized source bytes.
4. Derived fields must carry source authority refs or digests so the verifier can confirm they did not drift.
5. A missing required digest is a blocker, not a warning.
6. A digest without included source bytes or a verified ledger anchor must be support-only or blocker-producing for claims that require authority.

## Missing-Evidence Blocker Vocabulary

| Blocker code | Meaning |
|---|---|
| `package_manifest_missing` | `manifest.json` absent from the witness package |
| `package_manifest_digest_mismatch` | recomputed package file digests do not match manifest digest material |
| `bundle_missing` | `outward_witness_bundle.json` absent from the witness package |
| `package_ref_outside_package` | a bundle or artifact package ref resolves outside the package root |
| `bundle_schema_missing_or_unsupported` | `schema_version` absent or not `outward_run.witness_bundle.v1` |
| `compare_scope_missing_or_unsupported` | `compare_scope` absent or unsupported |
| `operator_surface_missing` | `operator_surface` absent or unsupported |
| `run_authority_missing` | `run_authority` absent or `run_id` empty |
| `run_id_drift` | run ids do not align across bundle evidence |
| `approval_authority_missing` | approval authority absent when an approval-required tool was invoked |
| `approval_status_not_approved` | invoked approval entry is not approved |
| `effect_before_approval` | tool invocation is not after matching approval |
| `effect_before_admission` | tool invocation is not after run admission |
| `tool_args_digest_drift` | effect and approval args digest or tool name drift |
| `ledger_export_missing` | package lacks the full `ledger_export.v1` bytes required by `ledger_evidence` |
| `ledger_export_digest_mismatch` | packaged `ledger_export.v1` bytes do not match `ledger_export_digest` |
| `ledger_payload_bytes_missing` | a full ledger export omits event payload bytes needed to recompute event hashes |
| `ledger_chain_broken` | ledger event chain does not match `LEDGER_EXPORT_V1` semantics |
| `ledger_chain_hash_mismatch` | recomputed ledger hash does not match bundle evidence |
| `full_ledger_export_required` | claim requires absence or completeness, but package lacks a full canonical ledger export |
| `final_truth_missing` | terminal success evidence missing |
| `terminal_status_drift` | terminal status does not align across run authority and ledger evidence |
| `effect_evidence_missing` | required effect evidence absent |
| `committed_artifact_missing` | package lacks committed artifact bytes required by an effect claim |
| `artifact_digest_mismatch` | packaged artifact bytes do not match the artifact ref digest |
| `source_bytes_missing_for_digest` | digest is used as authority but source bytes or ledger anchor are absent |
| `model_invocation_digest_drift` | model invocation digest does not match anchored proposal evidence |
| `model_invocation_evidence_not_anchored` | model evidence exists but is not anchored to authority |
| `missing_authority_digest` | required digest or authority ref absent |
| `policy_tool_not_in_approval_required` | governed tool was not approval-required in policy identity |
| `claim_tier_not_supported` | requested posture exceeds available evidence |

## Package Producer Command Target

```bash
python scripts/proof/emit_outward_run_witness_package.py \
  --run-id <run_id> \
  --scope outward_run_write_file_approved_v1 \
  --output workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1
```

The producer reads persisted outward run records, approval records, run events, the full canonical `ledger_export.v1`, and committed artifact bytes. It must not consult model providers or network state.

## Offline Package Verifier Target

```bash
python scripts/proof/verify_outward_run_witness_package.py \
  --package workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1 \
  --scope outward_run_write_file_approved_v1 \
  --output benchmarks/results/proof/outward_run_witness_report.json
```

The verifier reads only files inside the witness package. It must not open the outward SQLite store, call the Orket API, read mutable workspace paths outside the package, or make network requests. Its proof input is `--package` only; bundle-only use is limited to schema or introspection checks and cannot accept proof claims. If `scripts/proof/verify_outward_run_witness_bundle.py` remains for continuity, it is only a compatibility alias to the package verifier and keeps the same package-only proof boundary.

## Exit Criteria

1. a v1 outward run can emit a portable witness package using the producer command
2. the package can be verified from package bytes only using the verifier command
3. missing source bytes, missing full ledger export, or digest-only evidence cannot produce success-shaped verifier output
4. the bundle surface reuses existing trusted-run vocabulary where it fits
5. this contract is extracted to `docs/specs/OUTWARD_RUN_WITNESS_V1.md` before implementation scripts depend on it
