# Multi-Agent Trust Handoff Packet 1 Implementation Plan

Last updated: 2026-05-04
Status: Active implementation lane
Owner: Orket Core

Accepted requirements: `docs/projects/archive/multiagent/2026-05-04-PACKET1-CLOSEOUT/MULTI_AGENT_TRUST_HANDOFF_REQUIREMENTS_V1.md`

## Authority Posture

This plan is the active roadmap authority for implementing Packet 1 only. The requirements document is accepted lane authority, not an active durable contract. Durable-contract promotion must be a same-change authority update and must not claim implementation completion before the proof envelope passes.

Primary durable authority dependencies:

1. `CURRENT_AUTHORITY.md`
2. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
3. `docs/specs/EXTENSION_CAPABILITY_AUTHORIZATION_V1.md`
4. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
5. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
6. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
7. `docs/specs/LEDGER_EXPORT_V1.md`

## Purpose

Implement Packet 1 multi-agent trust handoff: A's source proof ends at committed output, the host packages that source proof, and B verifies the package before first turn. The implementation must make source output, source policy identity, package integrity, and B admission ordering independently checkable from packaged bytes.

## Bounded Scope

This lane includes:

1. resolving the outward-witness prerequisite for committed-output and source-policy identity authority,
2. producing a host-managed handoff envelope package for one source run and one target agent,
3. implementing an offline verifier that accepts packaged bytes only,
4. implementing B's `handoff_required` admission gate with materialized minimal durable rejection records,
5. adding B-side `trust_handoff_verified` and `trust_handoff_rejected` ledger events,
6. adding the proof scripts, corruption suite, API tests, and runtime admission tests named by the requirements.

This lane does not include signing, HMAC, PKI, chaining, multi-hop audit, k-of-N approval, delegation chains, inter-host trust, policy negotiation, expiry windows, nonces, memory handoff, or B emitting handoff envelopes.

## Current Authority Context

As of 2026-05-04:

1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` guarantees `run_authority.policy_overrides_digest`.
2. `policy_identity` is guaranteed as an outward witness object, but exact sub-fields are not currently durable verifier vocabulary for this lane.
3. Packet 1 therefore treats `source_policy_digest` as A's approved source policy identity digest and anchors it to `source_outward_witness_bundle.json#/run_authority/policy_overrides_digest` unless the outward witness contract is updated in the same change.
4. `commitment_recorded.payload.committed_output_digest` may not exist on every current outward ledger fixture, so the outward witness output-anchor path must remain available unless the ledger export or outward witness contract is updated truthfully.
5. The requirements document is not an implementation-complete claim and is not an active durable contract.

## Governing Decisions

1. Packet 1 compare scope is exactly `trust_handoff.packet1.single_output_policy_compat.v1`.
2. The host is the sole envelope authority; Packet 1 uses SHA-256 envelope digest only and does not introduce signatures, HMAC, or PKI.
3. Source ledger authority ends at `commitment_recorded`; handoff issuance events are excluded from `source_ledger_export_digest`.
4. B may create a minimal durable admission `RunRecord`, but rejected admission must not create `run_started`, `turn_started`, model invocation, tool invocation, memory write, or commitment events.
5. The offline verifier must consume packaged bytes only and keep first-failing-reason semantics.
6. Package integrity uses framed `trust_handoff_package_digest_material.v1` with path, byte length, and SHA-256 for each declared file.
7. Workstreams 2 through 5 must not begin until Workstream 1 exit criteria pass, except for non-authoritative scaffolding that does not encode verifier field paths.

## Workstream 0 - Authority Handoff

### Goal

Move the requirements into an active project lane and make this plan the roadmap target.

Workstream 0 is a same-change prerequisite for marking this plan as the active implementation lane. This plan must not be treated as active unless the requirements document is at `docs/projects/multiagent/MULTI_AGENT_TRUST_HANDOFF_REQUIREMENTS_V1.md`, the roadmap `Priority Now` entry points to this plan, and the Project Index includes `docs/projects/multiagent/`.

### Tasks

1. move the requirements document from `docs/projects/future/multiagent/` to `docs/projects/multiagent/`,
2. add this implementation plan as the canonical active lane path,
3. put the lane in `docs/ROADMAP.md` under `Priority Now`,
4. add `docs/projects/multiagent/` to the Project Index,
5. run `python scripts/governance/check_docs_project_hygiene.py`.

### Exit Criteria

1. `docs/projects/multiagent/` exists as the active non-archive project folder,
2. the roadmap `Priority Now` entry points to this implementation plan,
3. the requirements document points to this implementation plan,
4. docs project hygiene passes.

## Workstream 1 - Contract Prerequisite And Durable Authority Alignment

### Goal

Close the field-path and authority prerequisites before implementing runtime behavior.

### Tasks

1. audit `OUTWARD_RUN_WITNESS_V1.md`, `SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`, and `LEDGER_EXPORT_V1.md` for committed-output and source-policy identity authority paths,
2. update `OUTWARD_RUN_WITNESS_V1.md` and its verifier fixtures in the same change if Packet 1 relies on fields not currently guaranteed,
3. decide whether Packet 1 keeps `source_policy_digest=run_authority.policy_overrides_digest` or promotes a stronger policy snapshot digest through durable contract changes,
4. define the exact outward witness committed-output artifact reference shape used by the source-output anchor path,
5. extract or promote any durable handoff contract into `docs/specs/` before runtime code depends on it,
6. update `CURRENT_AUTHORITY.md` only if a handoff spec is promoted to active durable contract.

### Exit Criteria

1. every verifier field path has a durable authority source,
2. no fixture-only policy or artifact path is treated as authority,
3. outward witness fixtures cover positive and negative cases for source policy identity digest and committed-output artifact reference evidence required by Packet 1,
4. any durable-contract promotion is reflected in the canonical authority snapshot.

## Workstream 2 - Handoff Package Emitter

### Goal

Create the host-side proof package for one source run and one target agent.

### Tasks

1. implement `scripts/proof/emit_trust_handoff_envelope.py`,
2. package `manifest.json`, `handoff_bundle.json`, `source_ledger_export.json`, `source_outward_witness_bundle.json`, `compatibility_scope.json`, and `artifacts/committed_output`,
3. compute canonical `envelope_digest`,
4. compute framed `trust_handoff_package_digest_material.v1`,
5. reject source ledger exports that contain handoff issuance events,
6. keep emitted package output stable at `benchmarks/results/proof/trust_handoff_envelope_package.v1`.

### Exit Criteria

1. emitted packages are deterministic for identical source bytes,
2. package references remain inside the package root,
3. undeclared files are not included,
4. package bytes contain enough evidence for offline verification without database or network access.

## Workstream 3 - Offline Verifier And Corruption Suite

### Goal

Implement byte-only verification and prove fail-closed behavior.

### Tasks

1. implement `scripts/proof/verify_trust_handoff_envelope.py`,
2. implement first-failing-reason verifier checks in the required order,
3. emit `trust_handoff_verifier_report.v1`,
4. include `key_authority_note=envelope_digest_is_sha256_not_hmac_or_asymmetric_signature`,
5. implement `scripts/proof/run_trust_handoff_corruption_suite.py`,
6. split corruption handling into `outer_integrity_corruption` and `rewrapped_semantic_corruption`,
7. add report conformance coverage for `key_authority_note_missing`.

### Exit Criteria

1. accepted packages pass every invariant,
2. corrupted packages produce zero accepted results,
3. semantic corruptions reach the intended reason code after deliberate rewrapping,
4. verifier execution is side-effect free with respect to runtime state,
5. `benchmarks/results/proof/trust_handoff_verifier_report.json` is produced by the verifier command,
6. `benchmarks/results/proof/trust_handoff_corruption_report.json` is produced by the corruption suite.

## Workstream 4 - Runtime Admission Enforcement

### Goal

Make B fail closed before first turn when `handoff_required: true`.

### Tasks

1. add B acceptance contract fields for `handoff_required`, `handoff_policy_compatibility_scope_id`, `handoff_envelope_package_path`, and `expected_source_agent_id`,
2. implement package verification at the `run_submitted` to `run_started` admission boundary,
3. emit `trust_handoff_verified` before `run_started` on success,
4. emit terminal `trust_handoff_rejected` and final truth on failure,
5. ensure failed admission creates no `run_started`, `turn_started`, model invocation, tool invocation, memory write, or commitment events,
6. add contract tests in `tests/kernel/v1/test_trust_handoff_admission.py`.

### Exit Criteria

1. verified handoff admission reaches normal run start,
2. rejected handoff admission remains inspectable as a minimal durable admission run,
3. failed admission cannot execute model, tool, memory, or commitment paths,
4. ordering violations are test-covered.

## Workstream 5 - Interface And API Surface

### Goal

Expose the handoff-required admission path through the existing runtime interfaces without widening Packet 1.

### Tasks

1. add API request validation for B's handoff acceptance fields,
2. resolve operator-registered compatibility scope before admission verification,
3. return distinct rejection reason and class for incomplete acceptance contracts,
4. add `tests/interfaces/test_api_trust_handoff.py`,
5. keep package paths host-managed and locator-only in ledger events.

### Exit Criteria

1. API submission can require handoff admission,
2. incomplete handoff contracts fail closed with `handoff_acceptance_contract_incomplete`,
3. API tests prove success and rejection paths without relying on narration or logs.

## Workstream 6 - Proof Closure

### Goal

Close the lane only after the required proof envelope is green or truthfully reported blocked.

### Required Commands

1. `python scripts/proof/emit_trust_handoff_envelope.py --source-run-id <id> --target-agent-id <id> --scope-id <id> --out benchmarks/results/proof/trust_handoff_envelope_package.v1`
2. `python scripts/proof/verify_trust_handoff_envelope.py --package benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_verifier_report.json`
3. `python scripts/proof/run_trust_handoff_corruption_suite.py --base benchmarks/results/proof/trust_handoff_envelope_package.v1 --out benchmarks/results/proof/trust_handoff_corruption_report.json`
4. `python -m pytest -q tests/kernel/v1/test_trust_handoff_admission.py`
5. `python -m pytest -q tests/interfaces/test_api_trust_handoff.py`
6. `python scripts/governance/check_docs_project_hygiene.py`

### Exit Criteria

1. all required commands pass, or blockers are recorded with observed path and observed result,
2. proof output paths are stable and rerunnable,
3. runtime and verifier claims match the accepted requirements,
4. roadmap and authority docs reflect the final lane state,
5. no Packet 2 feature is implemented or implied.

## Remaining Blockers Before Runtime Work

1. Confirm whether `source_policy_digest` remains `policy_overrides_digest` or requires a new durable policy snapshot digest.
2. Confirm or update the outward witness committed-output artifact reference shape before treating it as source-output authority.
3. Decide whether the handoff requirements become an active durable spec under `docs/specs/` before implementation begins.
