# Trust Handoff Packet 1 V1

Last updated: 2026-05-04
Status: Active durable contract
Owner: Orket Core

Canonical implementation:
1. `orket/application/services/trust_handoff_verifier.py`
2. `orket/application/services/trust_handoff_admission.py`
3. `scripts/proof/emit_trust_handoff_envelope.py`
4. `scripts/proof/verify_trust_handoff_envelope.py`
5. `scripts/proof/run_trust_handoff_corruption_suite.py`

Related authority:
1. `CURRENT_AUTHORITY.md`
2. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
3. `docs/specs/LEDGER_EXPORT_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
5. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`

## Scope

Packet 1 implements one source governed outward run and one target governed outward run.

In scope:
1. host-issued handoff envelope packages,
2. SHA-256 envelope and package integrity,
3. offline byte-only verification,
4. B-side `handoff_required` admission before `run_started`,
5. B-side `trust_handoff_verified` and `trust_handoff_rejected` ledger events.

Out of scope:
1. HMAC, asymmetric signatures, PKI, or host identity proof,
2. multi-hop chains,
3. B emitting a downstream envelope,
4. k-of-N approval, delegation, federation, policy negotiation, expiry windows, nonces, or memory handoff.

## Fixed Decisions

1. Compare scope is `trust_handoff.packet1.single_output_policy_compat.v1`.
2. Package schema version is `trust_handoff_envelope_package.v1`.
3. Bundle schema version is `trust_handoff.bundle.v1`.
4. Verifier report schema version is `trust_handoff_verifier_report.v1`.
5. Compatibility scope schema version is `handoff_policy_compatibility_scope.v1`.
6. Envelope authority is `SHA-256(canonical handoff_bundle.json without envelope_digest)`.
7. The verifier report must include `key_authority_note=envelope_digest_is_sha256_not_hmac_or_asymmetric_signature`.
8. Packet 1 source policy identity is `source_outward_witness_bundle.json#/run_authority/policy_overrides_digest`.
9. Packet 1 source output authority accepts the outward witness committed-output artifact reference shape defined in `docs/specs/OUTWARD_RUN_WITNESS_V1.md`.
10. The runtime uses the target B outward `run_id` as the host-declared target agent identity for Packet 1 admission; package `target_agent_id` must match that `run_id`.
11. The package carries the host-managed `compatibility_scope.json` bytes. B resolves the scope by matching `handoff_policy_compatibility_scope_id` from the acceptance contract to the packaged scope id before admitting the run.

## Package Layout

```text
trust_handoff_envelope_package.v1/
  manifest.json
  handoff_bundle.json
  source_ledger_export.json
  source_outward_witness_bundle.json
  compatibility_scope.json
  artifacts/
    committed_output
```

The package may contain no undeclared files. `manifest.json` is special package metadata and is not part of package digest material. Every non-manifest file must be declared by the manifest.

Required manifest fields:
1. `schema_version`
2. `package_id`
3. `source_run_id`
4. `target_agent_id`
5. `bundle_path`
6. `ledger_export_path`
7. `source_witness_bundle_path`
8. `compatibility_scope_path`
9. `artifact_paths.committed_output`
10. `package_digest`
11. `issued_at_iso`

`package_digest` is SHA-256 over canonical JSON:

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

The `files` array is sorted by package-relative path and includes every manifest-declared non-manifest file.

## Bundle Authority

Required `handoff_bundle.json` fields:
1. `schema_version`
2. `bundle_id`
3. `source_run_id`
4. `source_agent_id`
5. `target_agent_id`
6. `handoff_policy_compatibility_scope_id`
7. `committed_output_digest`
8. `committed_output_path_hint`
9. `source_policy_digest`
10. `source_policy_identity.policy_digest`
11. `approval_record_digest`
12. `approval_id`
13. `commitment_record_digest`
14. `ledger_export_digest`
15. `source_witness_bundle_digest`
16. `ledger_event_count`
17. `compare_scope`
18. `envelope_digest`
19. `produced_at_iso`

The envelope digest excludes only `envelope_digest` from the canonicalized bundle object.

## Verification Order

The offline verifier must stop at the first failing reason in this order:
1. manifest schema and required fields,
2. manifest path containment and required file existence,
3. undeclared package file absence,
4. package digest,
5. bundle schema and compare scope,
6. envelope digest,
7. source ledger digest,
8. full `ledger_export.v1` validity and event count,
9. source outward witness digest and alignment,
10. approved proposal payload digest,
11. commitment payload digest,
12. approval-before-commitment ordering,
13. post-approval denial or policy-rejection absence,
14. committed output artifact digest,
15. source output anchor,
16. source policy anchor,
17. compatibility scope schema and digest,
18. source policy compatibility,
19. source agent admission,
20. source policy identity equality,
21. target agent identity equality,
22. source run id equality.

Accepted reports must have `result=accepted`, no rejection reason, and a stable invariant signature over check ids and statuses. Rejected reports must carry one reason and one class from the Packet 1 failure vocabulary.

## B Admission Contract

B activates Packet 1 admission by setting:
1. `task.acceptance_contract.handoff_required=true`
2. `task.acceptance_contract.handoff_policy_compatibility_scope_id`
3. `task.acceptance_contract.handoff_envelope_package_path`
4. `task.acceptance_contract.expected_source_agent_id`

When `handoff_required=true` and any required field is absent, B must fail closed with:
1. `trust_handoff_rejected`
2. `rejection_reason=handoff_acceptance_contract_incomplete`
3. terminal `run_completed` with `outcome=handoff_rejected`
4. no `run_started`, `turn_started`, model invocation, tool invocation, memory write, or commitment event.

On success, B emits `trust_handoff_verified` before `run_started`.

## Ledger Events

`trust_handoff_verified` payload fields:
1. `bundle_id`
2. `source_run_id`
3. `source_agent_id`
4. `committed_output_digest`
5. `source_policy_digest`
6. `handoff_policy_compatibility_scope_id`
7. `envelope_digest`
8. `package_path`

`trust_handoff_rejected` payload fields:
1. `rejection_reason`
2. `rejection_class`
3. `bundle_id`
4. `source_run_id`
5. `package_path`
6. `result_class=handoff_rejected`
7. `evidence_sufficiency=evidence_sufficient`

## Proof Commands

Required Packet 1 proof envelope:
1. `python scripts/proof/emit_trust_handoff_envelope.py --source-run-id <id> --target-agent-id <id> --scope-id <id> --out benchmarks/results/proof/trust_handoff_envelope_package.v1`
2. `python scripts/proof/verify_trust_handoff_envelope.py --package benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_verifier_report.json`
3. `python scripts/proof/run_trust_handoff_corruption_suite.py --base benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_corruption_report.json`
4. `python -m pytest -q tests/kernel/v1/test_trust_handoff_admission.py`
5. `python -m pytest -q tests/interfaces/test_api_trust_handoff.py`

## Maintenance

Any change to package fields, verifier ordering, failure vocabulary, B admission fields, or ledger event payload shape must update this spec, `CURRENT_AUTHORITY.md`, and affected proof tests in the same change.
