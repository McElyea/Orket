# Multi-Agent Trust Handoff Requirements V1

Last updated: 2026-05-04
Status: Accepted requirements -- active implementation lane companion; durable Packet 1 contract promoted to `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`
Owner: Orket Core

Implementation plan: `docs/projects/archive/multiagent/2026-05-04-PACKET1-CLOSEOUT/MULTI_AGENT_TRUST_HANDOFF_IMPLEMENTATION_PLAN.md`

Requirements scope: Packet 1 only — A's source proof ends at committed output, the host packages that source proof, B verifies before first turn, one committed output, one policy-compatibility check, two-agent chain.

Related authority:
1. `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`
2. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
3. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
4. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
5. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
6. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
7. `docs/specs/LEDGER_EXPORT_V1.md`
8. `CURRENT_AUTHORITY.md`

Implementation prerequisite:
1. Packet 1 implementation depends on `docs/specs/TRUST_HANDOFF_PACKET1_V1.md` plus the outward witness source anchors now documented in `docs/specs/OUTWARD_RUN_WITNESS_V1.md`.

Implementation is reopened through `docs/ROADMAP.md` for the scoped Packet 1 lane. Any scope change, durable-contract promotion, or Packet 2 work still requires an explicit scoped implementation request.

---

## Purpose

Define the requirements for multi-agent trust handoff so a governed run produced by one Orket agent (A) can be consumed as authoritative input by a second governed run (B), without requiring B to trust A's narration, logs, or wrapper summaries.

The trust handoff envelope is the mechanism that makes the outward proof kernel composable across agent boundaries. A later chain of N agents, each producing a ledger-anchored handoff envelope, can form a traceable, tamper-evident pipeline. Packet 1 proves only the first two-agent slice without requiring B to trust A's self-report.

This spec defines what the handoff envelope must contain, how key and envelope authority is established, how B verifies policy compatibility before its first turn, how timing and fail-closed behavior are enforced at B's admission boundary, and what the offline verifier may consume.

---

## Non-Goals

This spec does not:

1. define a general approval platform or multi-hop routing table,
2. claim the handoff mechanism proves model output correctness or provider semantics,
3. replace trusted-run witness, outward-run witness, or supervised-run approval-checkpoint contracts,
4. introduce per-agent PKI, certificate authorities, or asymmetric key infrastructure (deferred to Packet 2),
5. define B's internal governed turn or tool dispatch behavior beyond the admission boundary,
6. define what B may produce or emit as a downstream handoff (chaining is a Packet 2 concern),
7. require network services, cloud credentials, or sandbox resource creation for verifier operation,
8. widen the public trust boundary defined by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`,
9. define a replacement-attempt resume path or a continuation authority for B beyond its normal governed run lifecycle.

---

## Packet 1 Decision Lock

The following are fixed for Packet 1 and must not be changed without a new explicit implementation request:

1. Two agents only: one source producer (A) and one verifier-consumer (B).
2. A must be a completed, committed, single-output outward governed run with a full source ledger export whose handoff authority boundary is the committed output. The source export must include the `commitment_recorded` event and must not include any handoff issuance event in A's `source_ledger_export_digest`.
3. B verifies the handoff envelope before its first model turn. No exceptions.
4. The host is the sole envelope authority. No per-agent keys, no inter-host trust, no federated authority.
5. The envelope digest is a SHA-256 commitment over canonical envelope bytes, anchored to A's committed source proof. No HMAC or asymmetric signature in Packet 1 (see §Key and Envelope Authority).
6. Policy compatibility is a single named scope check at B's admission boundary. One scope, one check.
7. The offline verifier consumes packaged bytes only. It may not open databases, make network requests, consult clocks, or read process environment for proof-bearing claims.
8. B fails closed with a distinct terminal stop reason if the handoff envelope is absent, malformed, digest-mismatched, or policy-incompatible. B must never reach `turn_started` on a failed handoff.
9. Packet 1 does not define a chaining surface. B cannot emit a handoff envelope over its own output. That is Packet 2.
10. Packet 1 does not define k-of-N multi-approval, delegation chains, or trust federation.

---

## Concepts and Vocabulary

**Agent A (source producer):** The governed run that produced the committed output. A is an outward governed run that has reached `commitment_recorded` with a full source ledger export available. A's Packet 1 authority ends at the committed output recorded by `commitment_recorded`.

**Agent B (consumer):** The governed run that intends to consume A's committed output as its authoritative input. B cannot begin its first model turn until it has verified A's handoff envelope.

**Handoff envelope:** The host-issued, ledger-anchored artifact that records A's committed output digest, A's policy identity, the binding between A and B, and the host's envelope integrity commitment. The envelope is NOT a runtime narration or a summary. It is a structured commitment over serialized authority.

**Handoff envelope package:** The self-contained directory of bytes that the offline verifier consumes. It includes the envelope, A's full source ledger export, A's committed output bytes, and a package manifest with a package digest.

**Policy compatibility scope:** A named operator-registered contract declaring which source policy identity digests B will accept from A. B's verifier checks A's `source_policy_digest` against the admitted scope before accepting the envelope.

**Envelope digest:** SHA-256 over canonical envelope bytes (defined in §Canonical Envelope Serialization). Not an HMAC. Not an asymmetric signature. The envelope authority derives from ledger anchoring, not from a signing key, in Packet 1.

**Handoff admission:** The act of B's runtime verifying the handoff envelope at B's `run_submitted`-to-`run_started` boundary. Success allows B to proceed. Failure terminates B with `trust_handoff_rejected` before any model turn.

**Ledger-anchored:** A field or claim is ledger-anchored when it is derivable from A's full canonical source `ledger_export.v1` with `export_scope=all`, as defined by `docs/specs/LEDGER_EXPORT_V1.md`, or from a verified outward witness bundle whose own ledger evidence matches that source ledger export. The derivation path must be explicit in the envelope.

**Admitted Packet 1 compare scope:** `trust_handoff.packet1.single_output_policy_compat.v1`.

---

## Key and Envelope Authority

### Rationale

Packet 1 does not introduce a signing key infrastructure. The reasons are:

1. A's committed output is already source-proof anchored by the outward ledger export and outward witness evidence that produced A's output.
2. Introducing a separate signing key requires key distribution, rotation, revocation, and a root-of-trust story. These are load-bearing problems that belong in a dedicated packet.
3. The offline verifier can prove structural, ledger, witness, and package integrity from packaged bytes alone, without a key. That is sufficient for Packet 1's stated claim: that B verified A's committed output digest, A's approval chain, and A's policy identity before starting.

### Packet 1 Envelope Authority Model

The envelope digest is computed as:

```
envelope_digest = SHA-256(canonical_envelope_bytes)
```

where `canonical_envelope_bytes` is the UTF-8 encoding of the canonical JSON form of the envelope object excluding the `envelope_digest` field itself, with keys sorted lexicographically, no whitespace, and no trailing newline (see §Canonical Envelope Serialization).

Authority is established by:

1. **Ledger anchoring of A's output.** The envelope's `commitment_record_digest` must match the digest of the `commitment_recorded` event in A's full source ledger export. The offline verifier recomputes this from the packaged ledger bytes.
2. **Approved proposal anchoring.** The envelope's `approval_record_digest` must match the digest of the `proposal_approved` event in A's ledger. No approved event means no authority.
3. **Output content anchoring.** The envelope's `committed_output_digest` must equal SHA-256 of the committed output bytes included in the package. The verifier must also prove that digest by one admitted source-output anchor path in §Source Output Anchor Rule.
4. **Source policy anchoring.** The envelope's `source_policy_digest` must be derivable from A's ledger-anchored outward witness evidence before it is checked against B's compatibility scope.
5. **Package manifest integrity.** The `package_digest` in the manifest is SHA-256 over canonical JSON package digest material that frames each authority file by path, byte length, and SHA-256 digest. The verifier recomputes this before accepting any individual file claim.
6. **Host issuance seam.** The host constructs and persists the envelope before signaling admission to B. The host is the sole issuer. B's runtime admission check reads the envelope from the host-managed package path.

The envelope digest is self-consistency evidence. It is not key-based authority. An evaluator verifying the package offline can confirm that the envelope bytes have not been modified after the host computed the digest, but they cannot confirm host identity from the digest alone. That limitation must be stated explicitly in the verifier report.

### Source Ledger Boundary

Packet 1 source proof authority ends at A's committed output recorded by `commitment_recorded`. The `source_ledger_export.json` included in the handoff package must include `commitment_recorded`, may include ordinary source-run closure events such as `turn_completed` or `run_completed`, and must not contain `trust_handoff_emitted` or any other handoff issuance event. A-side awareness of a downstream consumer is deferred unless a later packet defines a separate handoff issuance ledger or host attribution log that is explicitly excluded from `source_ledger_export_digest`.

### Source Output Anchor Rule

The verifier accepts exactly two source-output anchor paths:

1. `commitment_recorded.payload.committed_output_digest` equals `handoff_bundle.committed_output_digest`, or
2. `source_outward_witness_bundle.json` is verified against the same source ledger export and names `artifacts/committed_output` with an authority artifact digest equal to `handoff_bundle.committed_output_digest`.

If neither path succeeds, the verifier fails with `committed_output_not_ledger_anchored`.

### Source Policy Anchor Rule

Before policy compatibility is checked against B's scope, the verifier must prove that `handoff_bundle.source_policy_digest` is derived from A's source evidence. For Packet 1, `source_policy_digest` means A's approved source policy identity digest. Under the current outward witness authority, that digest is `policy_overrides_digest`; it is not a full policy snapshot digest unless `docs/specs/OUTWARD_RUN_WITNESS_V1.md` later defines those digests as equivalent or exposes a distinct verifier-readable policy snapshot digest.

The derivation path must be one of the admitted Packet 1 source-policy evidence paths listed here. Implementations must not infer policy identity from free-form summaries, display names, witness report prose, or fixture-only fields.

Packet 1 admits this source-policy anchor:

1. `source_outward_witness_bundle.json#/run_authority/policy_overrides_digest` must equal `handoff_bundle.source_policy_digest`.

The following candidate paths are not active verifier vocabulary in this draft because the current related authority does not guarantee them as exact policy digest paths. Implementation must either keep them out of Packet 1 or promote them by updating the related contracts and verifier fixtures in the same change before this spec is promoted:

1. `source_outward_witness_bundle.json#/policy_identity/<exact policy digest field>`.
2. `source_ledger_export.json#/<exact run or approval checkpoint policy digest path>`.
3. `source_outward_witness_bundle.json#/<exact policy snapshot digest path>`, if Packet 1 chooses a full policy snapshot digest instead of `policy_overrides_digest`.

If the source policy digest is absent from A's source evidence, the verifier fails with `source_policy_digest_not_ledger_anchored` and class `missing_evidence`. If A's source evidence carries a different policy digest, the verifier fails with `source_policy_digest_not_ledger_anchored` and class `identity_drift`.

### Packet 2 Forward Note (Non-Authoritative)

A later packet may introduce Ed25519 host signing. Under that model, the envelope digest field would be replaced by a detached signature over canonical envelope bytes, and the package manifest would carry the host's public verification key. The offline verifier would verify the signature. That packet must define key generation, rotation, out-of-band distribution, and revocation. Packet 1 does not carry any of those obligations.

---

## Accepted-Policy Compatibility

### Purpose

B must not consume output from A if A's governing policy is incompatible with B's admitted input constraints. Incompatible policy includes A having been approved under a policy that permits tool families or action scopes that B's operator has not accepted as a valid source authority.

### Compatibility Scope Contract

The operator registers a named `handoff_policy_compatibility_scope` before B is admitted. The scope is a JSON object with:

| Field | Type | Notes |
|---|---|---|
| `scope_id` | string | Stable operator-chosen identifier |
| `schema_version` | string | Must equal `handoff_policy_compatibility_scope.v1` |
| `admitted_source_policy_digests` | array of string | Approved source policy identity digest values |
| `admitted_source_agent_ids` | array of string | Agent id strings B will accept as source producers; empty means any declared agent id is admitted |
| `scope_digest` | string | SHA-256 over canonical scope bytes excluding this field |

B's acceptance contract must name exactly one `handoff_policy_compatibility_scope_id`. The runtime resolves the scope from the operator-registered scope contract before constructing the admission check.

The compatibility check passes when:

1. `envelope.source_policy_digest` is present in `admitted_source_policy_digests`, AND
2. if `admitted_source_agent_ids` is non-empty, `envelope.source_agent_id` is present in that list.

If the source policy digest check fails, B fails closed with `trust_handoff_policy_incompatible` and must not proceed. If the source agent id check fails, B fails closed with `trust_handoff_agent_not_admitted` and must not proceed.

### Scope Registration Path

The operator must register the scope before B's governed run is submitted. The scope is not mutable after registration. If the scope must change, the operator registers a new scope with a new `scope_id` and updates B's acceptance contract to reference the new scope.

Scope registration lives in the host-managed operator configuration surface, not in B's acceptance contract bytes. The acceptance contract carries only the `scope_id` reference, not the scope content. The runtime resolves the content at admission time.

The offline verifier package must include the scope contract bytes. The verifier recomputes the `scope_digest` and checks the compatibility condition from package bytes. The verifier does not consult the host configuration surface at verification time.

---

## Fail-Closed Timing

### Admission Boundary

B's admission boundary is the transition from `run_submitted` to `run_started`. The handoff verification must complete at this boundary. B must never advance past `run_submitted` without a verified, compatible handoff envelope when B's acceptance contract declares `handoff_required: true`.

The runtime must enforce this order:

```
run_submitted
  → resolve handoff_policy_compatibility_scope from acceptance contract
  → load handoff envelope package from host-managed path
  → verify package digest material
  → verify envelope digest over canonical bytes
  → verify commitment_record_digest against packaged ledger export
  → verify approval_record_digest against packaged ledger export
  → verify committed_output_digest against packaged artifact bytes
  → verify source output anchor
  → verify source policy digest anchor
  → verify policy compatibility scope check
  → emit trust_handoff_verified ledger event with envelope digest
  → run_started
```

If any step in this sequence fails, the runtime must:

1. emit `trust_handoff_rejected` as a ledger event on B's run, with `rejection_reason` and `rejection_class`,
2. record a terminal final truth for B's run with result class `handoff_rejected` and evidence sufficiency `evidence_sufficient`,
3. not advance to `run_started`, `turn_started`, or any model invocation,
4. not invoke any tool, write any memory, or produce any commitment.

The `trust_handoff_rejected` event is terminal. B's run is closed. No continuation, resume, or retry is admitted on the rejected handoff path in Packet 1.

### Timing Invariant

The handoff verification must be complete and its result must be recorded in B's ledger before B's first `turn_started` event. Any evidence of `turn_started` before `trust_handoff_verified` in B's ledger is a fatal ordering violation.

### `handoff_required` Acceptance Contract Field

B's acceptance contract must declare `handoff_required: true` to activate the admission boundary check. When `handoff_required` is absent or false, B operates as a normal governed run with no handoff enforcement. The field is not implied by other contract fields.

### Runtime Atomicity Requirement

When `handoff_required: true`, B may create a minimal durable admission `RunRecord` before the handoff check completes so failed governance remains inspectable. That admission run record must contain exactly one terminal admission result:

1. `trust_handoff_verified` followed by normal `run_started`, or
2. `trust_handoff_rejected` followed by terminal final truth.

Failed handoff admission must not create `run_started`, `turn_started`, tool invocation, memory write, or commitment events. B's `RunRecord` must not remain durable without either `trust_handoff_verified` or `trust_handoff_rejected`.

---

## Handoff Envelope Package Schema

### Package Layout

Schema version string: `trust_handoff_envelope_package.v1`

```
trust_handoff_envelope_package.v1/
  manifest.json
  handoff_bundle.json
  source_ledger_export.json
  source_outward_witness_bundle.json
  compatibility_scope.json
  artifacts/
    committed_output
```

All files are required. The package may contain no other files in Packet 1 except supplementary files declared in the manifest under `supplementary_paths`. Supplementary files are support-only and must not be treated as authority.

### `manifest.json` Schema

Required fields:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Must equal `trust_handoff_envelope_package.v1` |
| `package_id` | string | Host-assigned stable package identifier |
| `source_run_id` | string | A's run_id |
| `target_agent_id` | string | B's expected agent identity |
| `bundle_path` | string | Relative path to `handoff_bundle.json` |
| `ledger_export_path` | string | Relative path to `source_ledger_export.json` |
| `source_witness_bundle_path` | string | Relative path to `source_outward_witness_bundle.json` |
| `compatibility_scope_path` | string | Relative path to `compatibility_scope.json` |
| `artifact_paths` | object | Map of named artifact keys to relative paths |
| `artifact_paths.committed_output` | string | Relative path to `artifacts/committed_output` |
| `package_digest` | string | SHA-256 over canonical JSON `trust_handoff_package_digest_material.v1`; see §Package Digest Material |
| `issued_at_iso` | string | Metadata only; not ordering authority |

### `handoff_bundle.json` Schema

Schema version string: `trust_handoff.bundle.v1`

Required fields:

| Field | Type | Classification | Notes |
|---|---|---|---|
| `schema_version` | string | authority | Must equal `trust_handoff.bundle.v1` |
| `bundle_id` | string | derived | Host-assigned stable identifier |
| `source_run_id` | string | authority | A's run_id; must align with ledger export |
| `source_agent_id` | string | authority | A's declared agent identity |
| `target_agent_id` | string | authority | B's expected agent identity; B checks this against itself at admission |
| `handoff_policy_compatibility_scope_id` | string | authority | Named scope B resolves at admission time |
| `committed_output_digest` | string | authority | SHA-256 of A's committed output bytes; recomputed by verifier |
| `committed_output_path_hint` | string | metadata | A's original committed output path for human reference; not authority |
| `source_policy_digest` | string | authority | A's approved source policy identity digest; Packet 1 currently binds this to outward witness `run_authority.policy_overrides_digest`, and checks it against scope only after source anchoring |
| `source_policy_identity` | object | authority | Structured policy identity projection from A's witness; see §Policy Identity |
| `approval_record_digest` | string | authority | SHA-256 of the `proposal_approved` event payload bytes in A's ledger |
| `approval_id` | string | authority | A's approval_id for traceability |
| `commitment_record_digest` | string | authority | SHA-256 of the `commitment_recorded` event payload bytes in A's ledger |
| `ledger_export_digest` | string | authority | SHA-256 of A's full source ledger export bytes |
| `source_witness_bundle_digest` | string | authority | SHA-256 of `source_outward_witness_bundle.json` bytes |
| `ledger_event_count` | integer | authority | Total event count in A's ledger export; verifier checks against actual |
| `compare_scope` | string | authority | Must equal `trust_handoff.packet1.single_output_policy_compat.v1` |
| `envelope_digest` | string | authority | SHA-256 over canonical envelope bytes (this field excluded); see §Canonical Envelope Serialization |
| `produced_at_iso` | string | metadata | Not ordering authority |

### Policy Identity Sub-Object

`source_policy_identity` must include:

| Field | Type | Notes |
|---|---|---|
| `policy_snapshot_id` | string | A's policy snapshot id |
| `policy_digest` | string | Must equal `handoff_bundle.source_policy_digest` and use the same digest kind |
| `policy_family` | string | Named policy family for human traceability |
| `policy_version` | string | Policy version string |

The verifier checks that `source_policy_identity.policy_digest` equals `source_policy_digest`. A mismatch is a bundle integrity failure.

### `source_ledger_export.json`

Must be A's full canonical `ledger_export.v1` with `export_scope=all`, as defined by `docs/specs/LEDGER_EXPORT_V1.md`. Partial views cannot prove event absence or ordering completeness.

The verifier must recompute the SHA-256 of this file's bytes and check it against `handoff_bundle.ledger_export_digest`.

### `source_outward_witness_bundle.json`

Must be A's outward witness bundle for the committed-output source run. The verifier must recompute the SHA-256 of this file's bytes and check it against `handoff_bundle.source_witness_bundle_digest`.

The verifier must treat this bundle as aligned source witness authority only when:

1. `schema_version` is `outward_run.witness_bundle.v1`,
2. `run_id` matches `handoff_bundle.source_run_id`,
3. `compare_scope` is an admitted committed-output outward scope,
4. `ledger_evidence.ledger_export_digest` matches `handoff_bundle.ledger_export_digest`,
5. `artifact_refs` contains exactly one authority `committed_output` reference with a verifier-readable digest and package path.

The committed-output artifact digest inside this bundle is accepted as output authority only through §Source Output Anchor Rule; equality to `handoff_bundle.committed_output_digest` is evaluated there so output-anchor failures produce `committed_output_not_ledger_anchored`. The source policy digest inside this bundle is accepted as policy authority only through §Source Policy Anchor Rule; equality to `handoff_bundle.source_policy_digest` is evaluated there so policy-anchor failures produce `source_policy_digest_not_ledger_anchored`.

### `compatibility_scope.json`

Must be the full `handoff_policy_compatibility_scope.v1` object for the scope named in `handoff_bundle.handoff_policy_compatibility_scope_id`. The verifier recomputes the `scope_digest` from this file and checks the policy compatibility condition from its bytes.

### Canonical Envelope Serialization

The canonical envelope is the JSON encoding of the `handoff_bundle.json` object excluding the `envelope_digest` field, with:

1. keys sorted lexicographically at every level,
2. no whitespace (no spaces, no newlines),
3. UTF-8 encoding,
4. no trailing newline.

This is the same normalization rule used by the ODR canonical JSON contract (`odr_canonical_json_bytes`). Implementations must use the same canonicalization helper or a verified equivalent.

The `envelope_digest` is SHA-256 of these canonical bytes.

### Package Digest Material

The package digest is:

```
package_digest = SHA-256(canonical JSON of package_digest_material.v1)
```

The verifier constructs `package_digest_material.v1` from package files after resolving all manifest-declared paths:

```json
{
  "schema_version": "trust_handoff_package_digest_material.v1",
  "files": [
    {
      "path": "handoff_bundle.json",
      "length_bytes": 1234,
      "sha256": "..."
    }
  ]
}
```

The `files` array must include `bundle_path`, `ledger_export_path`, `source_witness_bundle_path`, `compatibility_scope_path`, every `artifact_paths` value, and every `supplementary_paths` value in deterministic path order. The verifier must reject package references that resolve outside the package root with `package_ref_outside_package`. The verifier must reject undeclared files with `unexpected_package_file`.

---

## Offline Verifier Contract

The offline handoff verifier must:

1. accept `--package <path>` as the only proof input that can produce `accepted`,
2. read only files inside the witness package supplied on the command line,
3. not open any database handle,
4. not make network requests,
5. not call model providers,
6. not read process environment for policy, credentials, or runtime configuration,
7. produce identical output for identical input bytes.

Bundle-only mode, if implemented for debugging or introspection, is schema-only and cannot produce `accepted`.

The verifier may import pure canonicalization and digest helpers (`odr_canonical_json_bytes`, `hashlib`, `binascii`) when those helpers do not consult mutable runtime state.

### Verifier Checks (Required, In Order)

1. Parse and validate `manifest.json` schema version.
2. Resolve all manifest-declared package paths; fail with `package_ref_outside_package` if any path escapes the package root. Missing required files fail with `bundle_missing`, `ledger_export_missing`, `source_witness_bundle_missing`, `compatibility_scope_missing`, or `committed_output_missing` as appropriate.
3. Check package contents contain no undeclared files except declared supplementary files; fail with `unexpected_package_file` on any deviation.
4. Recompute `package_digest` from `trust_handoff_package_digest_material.v1`; fail with `package_digest_mismatch` on any deviation.
5. Parse and validate `handoff_bundle.json` schema version and required fields.
6. Check `compare_scope` equals `trust_handoff.packet1.single_output_policy_compat.v1`; fail with `bundle_schema_invalid` on deviation.
7. Recompute `envelope_digest` over canonical envelope bytes (excluding that field); fail with `envelope_digest_mismatch` on deviation.
8. Load `source_ledger_export.json`; recompute its SHA-256 and check against `ledger_export_digest`; fail with `ledger_export_digest_mismatch` on deviation.
9. Verify `source_ledger_export.json` is a valid full canonical `ledger_export.v1` with `export_scope=all`; fail with `ledger_export_partial_view` if it is not full.
10. Check `ledger_event_count` against actual event count in the ledger export; fail with `ledger_event_count_mismatch` on deviation.
11. Load `source_outward_witness_bundle.json`; recompute its SHA-256 and check against `source_witness_bundle_digest`; fail with `source_witness_bundle_digest_mismatch` on deviation.
12. Validate the source outward witness bundle schema and its run id, compare scope, ledger evidence, and committed-output artifact reference presence and shape; fail with `source_witness_bundle_invalid` on schema, run-id, compare-scope, ledger-evidence, or artifact-reference shape drift. Committed-output digest equality and source-policy digest equality are evaluated only by the source output and source policy anchor checks below.
13. Locate the `proposal_approved` event in the ledger export; recompute its payload digest and check against `approval_record_digest`; fail with `approval_record_missing_or_drifted` if absent or mismatched.
14. Locate the `commitment_recorded` event in the ledger export; recompute its payload digest and check against `commitment_record_digest`; fail with `commitment_record_missing_or_drifted` if absent or mismatched.
15. Confirm ordering: `proposal_approved` must precede `commitment_recorded` in ledger event sequence; fail with `approval_before_commitment_ordering_violated` if not.
16. Confirm no `proposal_denied` or `proposal_policy_rejected` event appears for the same proposal identity after `proposal_approved`; fail with `post_approval_denial_present` if so.
17. Load `artifacts/committed_output`; recompute its SHA-256 and check against `committed_output_digest`; fail with `committed_output_digest_mismatch` on deviation.
18. Confirm one admitted source-output anchor path from §Source Output Anchor Rule; fail with `committed_output_not_ledger_anchored` if neither path succeeds.
19. Confirm `handoff_bundle.source_policy_digest` is anchored by A's source evidence under §Source Policy Anchor Rule; fail with `source_policy_digest_not_ledger_anchored` if absent or drifted.
20. Load `compatibility_scope.json`; recompute its `scope_digest` and check; fail with `compatibility_scope_digest_mismatch` on deviation.
21. Check `handoff_bundle.source_policy_digest` against `compatibility_scope.admitted_source_policy_digests`; fail with `trust_handoff_policy_incompatible` if not present.
22. If `compatibility_scope.admitted_source_agent_ids` is non-empty, check `handoff_bundle.source_agent_id`; fail with `trust_handoff_agent_not_admitted` if not present.
23. Check `handoff_bundle.source_policy_identity.policy_digest` equals `handoff_bundle.source_policy_digest`; fail with `policy_identity_digest_mismatch` if not.
24. Check that `target_agent_id` in the bundle matches `target_agent_id` in the manifest; fail with `target_agent_id_mismatch` if not.
25. Check that `source_run_id` in the bundle matches `source_run_id` in the manifest and appears in the ledger export `run_id` field; fail with `source_run_id_drift` if not.

All checks must pass for the verifier to return `accepted`. Any single failure returns `rejected` with the first failing reason code. The verifier must not suppress or combine failure codes.

When `source_witness_bundle_invalid` is returned, the verifier report detail must name the failed sub-check, such as `schema`, `run_id`, `ledger_export_digest`, `compare_scope`, or `committed_output_artifact_ref`.

### Envelope Key Authority Limitation Statement

The verifier report must include a `key_authority_note` field with the value `envelope_digest_is_sha256_not_hmac_or_asymmetric_signature`. This note records that the verifier has confirmed digest consistency but cannot confirm host identity from the digest alone, as key-based envelope signing is deferred to Packet 2.

### Verifier Report Schema

Schema version: `trust_handoff_verifier_report.v1`

Required fields:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Must equal `trust_handoff_verifier_report.v1` |
| `bundle_id` | string | |
| `source_run_id` | string | |
| `target_agent_id` | string | |
| `compare_scope` | string | |
| `result` | string | `accepted`, `rejected` |
| `rejection_reason` | string or null | First failing reason code; null when accepted |
| `rejection_class` | string or null | Failure class from §Failure Classes; null when accepted |
| `checks_performed` | array of objects | One entry per check with `check_id`, `passed`, `detail` |
| `key_authority_note` | string | Must equal `envelope_digest_is_sha256_not_hmac_or_asymmetric_signature` |
| `source_output_anchor_result` | object | `anchor_path`, `committed_output_digest`, `anchored` boolean |
| `source_policy_anchor_result` | object | `source_policy_digest`, `anchored` boolean, `source` |
| `policy_compatibility_result` | object | `scope_id`, `source_policy_digest`, `compatible` boolean |
| `invariant_signature` | string | Stable digest over check ids and statuses; excludes run-specific ids and timestamps |

---

## Ledger Events for Handoff

B's runtime must emit the following ledger events on B's run. Packet 1 does not define a required A-side `trust_handoff_emitted` event, because A's source proof boundary ends at `commitment_recorded`.

### `trust_handoff_verified`

Emitted when the handoff admission check passes before `run_started`.

Required fields:
1. `bundle_id` — A's handoff bundle id
2. `source_run_id` — A's run_id
3. `source_agent_id` — A's agent identity
4. `committed_output_digest` — SHA-256 of A's committed output bytes
5. `source_policy_digest` — A's approved source policy identity digest
6. `handoff_policy_compatibility_scope_id` — name of the scope that passed
7. `envelope_digest` — the envelope digest checked
8. `package_path` — host-managed package path (locator only, not proof authority)

### `trust_handoff_rejected`

Emitted when the handoff admission check fails before `run_started`. This event is terminal.

Required fields:
1. `rejection_reason` — first failing reason code
2. `rejection_class` — failure class
3. `bundle_id` or null — if the bundle was parseable before rejection
4. `source_run_id` or null — if extractable before rejection
5. `package_path` or null — host-managed package path, if resolved before rejection

---

## Invariants

Invariant namespace: `MATH-INV-*` (Multi-Agent Trust Handoff).

**MATH-INV-001:** An accepted handoff verifier report MUST have `schema_version=trust_handoff_verifier_report.v1`.

**MATH-INV-002:** An accepted handoff verifier report MUST have `result=accepted`.

**MATH-INV-003:** An accepted package MUST have a valid `manifest.json` with `schema_version=trust_handoff_envelope_package.v1`.

**MATH-INV-004:** The `package_digest` MUST be recomputed from canonical `trust_handoff_package_digest_material.v1` by the verifier and must equal the manifest-declared value.

**MATH-INV-005:** The `envelope_digest` in `handoff_bundle.json` MUST be recomputed from canonical envelope bytes by the verifier and must equal the bundle-declared value.

**MATH-INV-006:** The `ledger_export_digest` MUST be recomputed from `source_ledger_export.json` bytes by the verifier and must equal the bundle-declared value.

**MATH-INV-007:** The ledger export MUST have `export_scope=all`. Partial exports cannot prove event absence and must not be accepted.

**MATH-INV-008:** A `proposal_approved` event for A's proposal MUST be present in the ledger export. Its payload digest MUST equal `approval_record_digest`.

**MATH-INV-009:** A `commitment_recorded` event MUST be present in the ledger export. Its payload digest MUST equal `commitment_record_digest`.

**MATH-INV-010:** `proposal_approved` MUST precede `commitment_recorded` in ledger event sequence. Any ordering inversion MUST produce `approval_before_commitment_ordering_violated`.

**MATH-INV-011:** No `proposal_denied` or `proposal_policy_rejected` event MUST appear for the same proposal identity after `proposal_approved`.

**MATH-INV-012:** The `committed_output_digest` MUST be recomputed from `artifacts/committed_output` bytes and must equal the bundle-declared value.

**MATH-INV-013:** A's committed output MUST be anchored by one admitted Source Output Anchor Rule path. Output not anchored by either admitted path must not be accepted.

**MATH-INV-014:** `source_policy_digest` MUST appear in `compatibility_scope.admitted_source_policy_digests`. Any mismatch MUST produce `trust_handoff_policy_incompatible`.

**MATH-INV-015:** If `compatibility_scope.admitted_source_agent_ids` is non-empty, `source_agent_id` MUST appear in that list. Any mismatch MUST produce `trust_handoff_agent_not_admitted`.

**MATH-INV-016:** `source_policy_identity.policy_digest` MUST equal `source_policy_digest`. A mismatch MUST produce `policy_identity_digest_mismatch`.

**MATH-INV-017:** `target_agent_id` in the bundle MUST equal `target_agent_id` in the manifest. A mismatch MUST produce `target_agent_id_mismatch`.

**MATH-INV-018:** `source_run_id` MUST be consistent across the bundle, the manifest, and the ledger export `run_id` field. Any drift MUST produce `source_run_id_drift`.

**MATH-INV-019:** The offline verifier MUST be side-effect free with respect to workflow state. It must not write to databases, emit network requests, mutate process state, or advance B's governed run lifecycle.

**MATH-INV-020:** Bundle-only mode, if implemented, MUST NOT return `accepted`. It may return at most `schema_valid` or an equivalent non-proof status.

**MATH-INV-021:** B's `run_started` ledger event MUST be preceded by `trust_handoff_verified` in B's ledger when `handoff_required: true`. Any evidence of `run_started` or `turn_started` before `trust_handoff_verified` is a fatal ordering violation.

**MATH-INV-022:** B's `trust_handoff_rejected` event MUST be terminal. No `run_started`, `turn_started`, tool invocation, memory write, or commitment event may follow it on B's run.

**MATH-INV-023:** The verifier report MUST include `key_authority_note=envelope_digest_is_sha256_not_hmac_or_asymmetric_signature`. Absence of this field means the report does not conform to Packet 1 authority semantics.

**MATH-INV-024:** The verifier MUST NOT consult live databases, clocks, process environment, model providers, or network services for any check that contributes to `accepted`. All accepted evidence must be derivable from packaged bytes.

**MATH-INV-025:** The `invariant_signature` in the verifier report MUST be stable for equivalent successful evidence and MUST exclude run-specific identifiers, timestamps, and session-local paths from its computation.

**MATH-INV-026:** A's source ledger export MUST include the committed-output source boundary at `commitment_recorded` and MUST NOT include `trust_handoff_emitted` or any other handoff issuance event in the bytes committed by `source_ledger_export_digest`.

**MATH-INV-027:** The source outward witness bundle MUST be packaged, digest-checked, and aligned with A's source ledger export, source run id, and committed-output artifact reference shape before it contributes authority. Committed-output digest equality and source-policy digest equality are governed by MATH-INV-013 and MATH-INV-028.

**MATH-INV-028:** `source_policy_digest` MUST be anchored by A's source evidence before compatibility is checked against B's scope. Missing or drifted source policy evidence MUST produce `source_policy_digest_not_ledger_anchored`.

**MATH-INV-029:** All package references MUST resolve inside the package root, and all non-directory package files MUST be declared by the manifest as authority or supplementary support files.

---

## Failure Classes

Each rejection must be assigned to one of these classes:

| Class | Meaning |
|---|---|
| `missing_evidence` | A required file, field, or event is absent from the package |
| `digest_mismatch` | A recomputed digest does not match the declared value |
| `ordering_violation` | A required event ordering constraint is violated |
| `post_approval_contamination` | A denial or policy-rejection event follows an approval for the same proposal |
| `policy_incompatible` | A's source policy identity digest is not in B's admitted compatibility scope |
| `agent_not_admitted` | A's agent id is not in B's admitted agent id list |
| `identity_drift` | A declared identity field is inconsistent across bundle, manifest, or ledger |
| `schema_invalid` | A required file does not conform to its declared schema version |
| `scope_invalid` | The compatibility scope file fails its own digest check |
| `package_boundary` | A package path escapes the package root or undeclared files are present |
| `source_witness_invalid` | The source outward witness bundle is missing, digest-mismatched, or not aligned with A's source proof |
| `acceptance_contract_invalid` | B's handoff-required acceptance contract is incomplete |

---

## Missing Evidence Vocabulary

The required initial blocker vocabulary for the verifier, covering both structural and proof failures:

`package_manifest_missing`, `package_manifest_schema_invalid`, `package_ref_outside_package`, `unexpected_package_file`, `package_digest_mismatch`, `bundle_missing`, `bundle_schema_invalid`, `envelope_digest_mismatch`, `ledger_export_missing`, `ledger_export_digest_mismatch`, `ledger_export_partial_view`, `ledger_event_count_mismatch`, `source_witness_bundle_missing`, `source_witness_bundle_digest_mismatch`, `source_witness_bundle_invalid`, `approval_record_missing_or_drifted`, `commitment_record_missing_or_drifted`, `approval_before_commitment_ordering_violated`, `post_approval_denial_present`, `committed_output_missing`, `committed_output_digest_mismatch`, `committed_output_not_ledger_anchored`, `source_policy_digest_not_ledger_anchored`, `compatibility_scope_missing`, `compatibility_scope_schema_invalid`, `compatibility_scope_digest_mismatch`, `trust_handoff_policy_incompatible`, `trust_handoff_agent_not_admitted`, `policy_identity_digest_mismatch`, `target_agent_id_mismatch`, `source_run_id_drift`, `handoff_acceptance_contract_incomplete`, `key_authority_note_missing`.

---

## Negative Corruption Matrix

The verifier must fail closed for these package-level corruptions. Each corruption must produce the stated reason code and class.

Corruption modes:

| Mode | Meaning |
|---|---|
| `outer_integrity_corruption` | Mutate packaged bytes without recomputing outer manifest or envelope digests. Expected first failure is usually `package_digest_mismatch`. |
| `rewrapped_semantic_corruption` | Mutate inner content, then recompute only the outer package or envelope digests needed to reach the intended semantic check. The field under test remains invalid. |

| Corruption id | Corruption mode | Mutation | Expected reason code | Expected class |
|---|---|---|---|---|
| MATH-CORR-001 | `outer_integrity_corruption` | Remove or alter `manifest.json` | `package_manifest_missing` or `package_manifest_schema_invalid` | `missing_evidence` or `schema_invalid` |
| MATH-CORR-002 | `outer_integrity_corruption` | Modify any non-manifest file after manifest was written | `package_digest_mismatch` | `digest_mismatch` |
| MATH-CORR-003 | `rewrapped_semantic_corruption` | Alter `handoff_bundle.json` `schema_version` | `bundle_schema_invalid` | `schema_invalid` |
| MATH-CORR-004 | `rewrapped_semantic_corruption` | Alter any bundle field after `envelope_digest` was computed | `envelope_digest_mismatch` | `digest_mismatch` |
| MATH-CORR-005 | `rewrapped_semantic_corruption` | Replace `source_ledger_export.json` with a different run's export | `ledger_export_digest_mismatch` | `digest_mismatch` |
| MATH-CORR-006 | `rewrapped_semantic_corruption` | Truncate ledger export to remove `commitment_recorded` | `commitment_record_missing_or_drifted` | `missing_evidence` |
| MATH-CORR-007 | `rewrapped_semantic_corruption` | Truncate ledger export to remove `proposal_approved` | `approval_record_missing_or_drifted` | `missing_evidence` |
| MATH-CORR-008 | `rewrapped_semantic_corruption` | Swap `proposal_approved` and `commitment_recorded` event positions | `approval_before_commitment_ordering_violated` | `ordering_violation` |
| MATH-CORR-009 | `rewrapped_semantic_corruption` | Insert a `proposal_denied` event after `proposal_approved` for the same proposal | `post_approval_denial_present` | `post_approval_contamination` |
| MATH-CORR-010 | `rewrapped_semantic_corruption` | Replace `artifacts/committed_output` bytes with different bytes | `committed_output_digest_mismatch` | `digest_mismatch` |
| MATH-CORR-011 | `rewrapped_semantic_corruption` | Alter `committed_output_digest` in bundle without changing artifact bytes | `committed_output_digest_mismatch` (recomputed digest mismatch) | `digest_mismatch` |
| MATH-CORR-012 | `rewrapped_semantic_corruption` | Remove committed output anchoring from both admitted source-output anchor paths | `committed_output_not_ledger_anchored` | `missing_evidence` |
| MATH-CORR-013 | `rewrapped_semantic_corruption` | Replace `compatibility_scope.json` with a scope that does not admit A's policy | `trust_handoff_policy_incompatible` | `policy_incompatible` |
| MATH-CORR-014 | `rewrapped_semantic_corruption` | Alter A's source policy evidence and `source_policy_digest` consistently to a digest not admitted by the scope | `trust_handoff_policy_incompatible` | `policy_incompatible` |
| MATH-CORR-015 | `rewrapped_semantic_corruption` | Set `source_agent_id` to a value not in `admitted_source_agent_ids` when that list is non-empty | `trust_handoff_agent_not_admitted` | `agent_not_admitted` |
| MATH-CORR-016 | `rewrapped_semantic_corruption` | Set `source_policy_identity.policy_digest` to differ from `source_policy_digest` | `policy_identity_digest_mismatch` | `identity_drift` |
| MATH-CORR-017 | `rewrapped_semantic_corruption` | Set `target_agent_id` in bundle to differ from manifest | `target_agent_id_mismatch` | `identity_drift` |
| MATH-CORR-018 | `rewrapped_semantic_corruption` | Set `source_run_id` in bundle to differ from ledger export | `source_run_id_drift` | `identity_drift` |
| MATH-CORR-019 | `rewrapped_semantic_corruption` | Use partial `source_ledger_export.json` with `export_scope` not equal to `all` | `ledger_export_partial_view` | `missing_evidence` |
| MATH-CORR-020 | `rewrapped_semantic_corruption` | Alter `compatibility_scope.json` bytes after `scope_digest` was recorded | `compatibility_scope_digest_mismatch` | `digest_mismatch` |
| MATH-CORR-021 | `rewrapped_semantic_corruption` | Make `source_policy_digest` pass B's scope but differ from A's source evidence | `source_policy_digest_not_ledger_anchored` | `identity_drift` |
| MATH-CORR-022 | `outer_integrity_corruption` | Add an undeclared file under the package root | `unexpected_package_file` | `package_boundary` |
| MATH-CORR-023 | `rewrapped_semantic_corruption` | Point a manifest-declared package path outside the package root | `package_ref_outside_package` | `package_boundary` |

### Verifier Report Conformance Matrix

Report conformance tests validate verifier output rather than package input.

| Report id | Mutation | Expected reason code | Expected class |
|---|---|---|---|
| MATH-REPORT-001 | Remove `key_authority_note` from verifier report | `key_authority_note_missing` | `missing_evidence` |

---

## Runtime Enforcement Requirements

### B's Acceptance Contract

B's acceptance contract must support the following new fields for Packet 1:

| Field | Type | Required | Notes |
|---|---|---|---|
| `handoff_required` | boolean | No | Activates the admission boundary check. False or absent means no handoff enforcement. |
| `handoff_policy_compatibility_scope_id` | string | When `handoff_required: true` | Names the scope contract B resolves at admission time |
| `handoff_envelope_package_path` | string | When `handoff_required: true` | Host-managed path to the envelope package; resolved before admission |
| `expected_source_agent_id` | string | When `handoff_required: true` | The agent identity B expects as source; checked against bundle |

When `handoff_required: true` and any of `handoff_policy_compatibility_scope_id`, `handoff_envelope_package_path`, or `expected_source_agent_id` are absent, B's minimal durable admission run must fail closed with `trust_handoff_rejected`, reason `handoff_acceptance_contract_incomplete`, and terminal final truth. It must not create `run_started`.

### Fail-Closed Preconditions

B's runtime must fail closed when any of the following is missing, drifted, or contradictory:

1. `handoff_envelope_package_path` resolves to a readable package directory with a valid `manifest.json`
2. `package_digest` matches the recomputed `trust_handoff_package_digest_material.v1`
3. `envelope_digest` matches the recomputed digest of canonical bundle bytes
4. `ledger_export_digest` matches the recomputed digest of `source_ledger_export.json`
5. `proposal_approved` event present and digest-matched in the ledger export
6. `commitment_recorded` event present, digest-matched, and sequentially after `proposal_approved`
7. `committed_output_digest` matches the recomputed digest of `artifacts/committed_output`
8. `committed_output_digest` is anchored by one admitted Source Output Anchor Rule path
9. `source_policy_digest` is anchored by A's source evidence
10. `compatibility_scope_digest` matches the recomputed digest of `compatibility_scope.json`
11. `source_policy_digest` is present in `compatibility_scope.admitted_source_policy_digests`
12. `source_agent_id` matches `expected_source_agent_id` in B's acceptance contract
13. `target_agent_id` in the bundle matches the manifest and B's own declared agent identity
14. `source_run_id` is consistent across bundle, manifest, and ledger export

Failure on any precondition produces `trust_handoff_rejected` and terminates B's run.

### Evidence and Attribution Contract

B's `trust_handoff_verified` or `trust_handoff_rejected` event provides the Packet 1 handoff attribution trail. An operator can trace the handoff from A's committed source proof through B's admission without consulting narration or logs. A-side downstream-awareness events are deferred unless a later packet defines a separate handoff issuance ledger or host attribution log.

Packet 1 does not require the host to cross-validate A's and B's ledgers in a single operation. That is a Packet 2 chain-audit concern.

---

## Canonical Proof Entrypoints (Required at Implementation)

When this spec is implemented, the following commands must exist and pass before the lane can close:

1. `python scripts/proof/emit_trust_handoff_envelope.py --source-run-id <id> --target-agent-id <id> --scope-id <id> --out benchmarks/results/proof/trust_handoff_envelope_package.v1`
2. `python scripts/proof/verify_trust_handoff_envelope.py --package benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_verifier_report.json`
3. `python scripts/proof/run_trust_handoff_corruption_suite.py --base benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_corruption_report.json`
4. `python -m pytest -q tests/kernel/v1/test_trust_handoff_admission.py`
5. `python -m pytest -q tests/interfaces/test_api_trust_handoff.py`

The corruption suite must exercise every package corruption in §Negative Corruption Matrix and every report conformance case in §Verifier Report Conformance Matrix. Package corruption cases must produce zero accepted results.

---

## Deferred to Packet 2

The following are explicitly out of scope for Packet 1 and must not be implemented until a new packet is explicitly requested:

1. **Asymmetric envelope signing.** Ed25519 host signing, public-key distribution, rotation, and revocation.
2. **Chaining.** B emitting a handoff envelope over its own committed output for a downstream agent C.
3. **Multi-hop audit.** Cross-ledger chain audit across N agents in a single verifier operation.
4. **k-of-N quorum or consensus.** Multiple source producers whose output is combined before B's admission.
5. **Delegation chains.** A authorizing a sub-agent on its behalf.
6. **Inter-host trust.** Handoff envelopes crossing host authority boundaries.
7. **Policy negotiation.** Dynamic policy compatibility resolution at handoff time.
8. **Time-bounded envelopes.** Envelope expiry, replay-window enforcement, or nonce-based freshness.
9. **Memory handoff.** Trust handoff for memory state rather than a committed output artifact.

---

## Specification Maintenance Rules

If this spec changes materially before or during implementation:

1. update `Last updated` and record the change reason in a note at the bottom of this file,
2. if the compare scope string changes, update all references to it simultaneously,
3. if invariant ids change, update the negative corruption matrix and verifier check list in the same edit,
4. if this spec is promoted to `Active durable contract`, update `CURRENT_AUTHORITY.md` and `docs/ROADMAP.md` in the same change,
5. if Packet 1 relies on `source_outward_witness_bundle.json` fields not already guaranteed by `docs/specs/OUTWARD_RUN_WITNESS_V1.md`, update that spec and its verifier fixtures in the same change,
6. do not allow the admitted compare scope, verifier report schema version, package schema version, or outward witness authority dependency to drift from the invariant model.

---

## Open Questions (Non-Blocking for Requirements)

These questions do not block the requirements packet but should be resolved during implementation planning:

1. **Agent identity string format.** Should `source_agent_id` and `target_agent_id` be free-form strings, URNs, or structured identifiers? The requirement is consistency and non-ambiguity. The exact format is an implementation decision.
2. **Scope registration surface.** Where exactly does the operator register the compatibility scope — via the API, a config file, or a governance script? This affects the implementation surface but not the verifier contract.
3. **B's own agent id.** How does B know its own `agent_id` to check `target_agent_id` at admission? This should be derivable from B's acceptance contract or host configuration, not self-declared at admission time.
4. **Package path delivery.** How does the host deliver `handoff_envelope_package_path` to B's runtime before B's run is submitted? This is a sequencing concern for the submission API surface.

---

## Change Notes

1. 2026-05-04: Tightened Packet 1 source-policy anchoring, outward witness implementation prerequisites, durable rejected-admission semantics, package digest framing, and corruption/report conformance boundaries while keeping this requirements document draft and non-authoritative.
2. 2026-05-04: Clarified that Packet 1 `source_policy_digest` is the approved source policy identity digest currently anchored only by outward witness `run_authority.policy_overrides_digest`; demoted unguaranteed policy paths to implementation prerequisites and separated witness artifact shape validation from source output-anchor equality.
