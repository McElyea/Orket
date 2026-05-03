# Slice 05 - Non-Fixture Useful Slice

Last updated: 2026-05-01
Status: Archived slice plan - approved useful scope completed
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`

## Purpose

Select and prove one externally useful outward workflow that is not only fixture-bounded.

This slice is the route from a proof-capable outward pipeline to a broader public trust boundary if the evidence supports it.

## Selected Scope

Compare scope: `outward_run_write_file_approved_v1`

This scope was selected because it satisfies the candidate criteria:

1. Real operational task: an operator submits a run, the model proposes a `write_file` tool call, a human approves it, and a file is written.
2. Bounded effect surface: one file write under a workspace run path.
3. Deterministic validation: `sha256(committed_file_bytes)` from the witness package must match the `committed_output` artifact ref and connector result digest.
4. Repeatable compare scope: admitted runs are bounded by the same `write_file` approval proof contract.
5. Portable witness package: Slice 02 targets this scope first.
6. Negative corruption proof: Slices 03 and 04 are written against this scope first.
7. Human inspectability: one proposal, one approval decision, one connector effect, one committed artifact, and one terminal run.

The non-fixture run must originate from an operator-submitted API or CLI task through the normal outward run path. It must not be a hand-authored bundle, synthetic event list, or test-only producer path. The committed file content may be simple, but it must be produced through the governed connector path from a real approved model proposal.

## Non-Selected Scopes

1. `governed_tool_sequence` multi-turn path: useful but too much machinery before the single-turn proof kernel exists; captured in Slice 07.
2. Denial-only path: required negative proof, but it does not prove the approval-and-effect story.
3. Any scope requiring live model inference during verification: forbidden by the finite trust-kernel model boundary.

## Bounded Effect Surface

The effect is bounded to:
1. one `write_file` connector call,
2. one file written under `workspace/<namespace>/runs/<run_id>/` or an explicitly contracted workspace path,
3. one `tool_invoked` ledger event,
4. one `commitment_recorded` ledger event, and
5. one `artifact_refs` entry with role `committed_output`.

No database writes, network calls, external API effects, or sandbox resource creation are in scope for this compare scope.

## Deterministic Validator Target

```bash
python scripts/proof/validate_outward_write_file_committed.py \
  --package workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1 \
  --output benchmarks/results/proof/outward_write_file_validation.json
```

Validator checks:
1. `artifact_refs` contains exactly one `committed_output` entry.
2. The committed artifact exists inside the witness package under `artifacts/committed_output`.
3. `sha256(file_bytes)` from the package artifact equals the artifact digest.
4. The artifact digest aligns with the connector result digest in effect evidence.

Validator output schema: `outward_write_file_validator.v1`.

The validator may read the witness package only. It must not consult the outward store, API, or mutable workspace paths outside the package.

## Positive Proof Command Chain

```bash
python scripts/proof/emit_outward_run_witness_package.py \
  --run-id <run_id> \
  --scope outward_run_write_file_approved_v1 \
  --output workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1

python scripts/proof/validate_outward_write_file_committed.py \
  --package workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1 \
  --output benchmarks/results/proof/outward_write_file_validation_<run_id>.json

python scripts/proof/verify_outward_run_witness_package.py \
  --package workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1 \
  --scope outward_run_write_file_approved_v1 \
  --output benchmarks/results/proof/outward_run_witness_report_<run_id>.json
```

Positive proof artifact paths:

```text
workspace/<namespace>/runs/<run_id>/outward_run_witness_package.v1
benchmarks/results/proof/outward_write_file_validation_<run_id>.json
benchmarks/results/proof/outward_run_witness_report_<run_id>.json
```

## Negative Proof Command Chain

```bash
python scripts/proof/corrupt_outward_run_witness_package.py \
  --base tests/proof_fixtures/outward_run/base_approved_package \
  --corruption-id <ORP-CORR-NNN> \
  --output /tmp/corrupted_package

python scripts/proof/verify_outward_run_witness_package.py \
  --package /tmp/corrupted_package \
  --scope outward_run_write_file_approved_v1 \
  --output benchmarks/results/proof/corruption_report_<ORP-CORR-NNN>.json
```

Each report must return `result=rejected` and the expected failure code.

## Claim-Posture Ceiling

A single verifier report on this scope supports at most `outward_lab_only`.

Two or more reports with matching invariant signatures may support `outward_verifier_stable` after a campaign report exists.

Any public-trust posture requires a same-change update to `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`; this slice does not propose that update by itself.

## Immediate Blocker

The first implementation blocker is:

```text
tests/proof_fixtures/outward_run/base_approved_package/
```

That fixture must come from a real governed-run v1 witness package, not a hand-authored success-shaped object. Until it exists, Slices 02 through 04 can define contracts and scripts, but they cannot truthfully close.

## Exit Criteria

1. `outward_run_write_file_approved_v1` is selected explicitly
2. a real governed-run package fixture exists
3. the workflow has complete positive proof artifacts or a truthful blocker
4. the corruption suite covers the selected scope
5. public trust wording remains unchanged unless the trust contract is updated truthfully in the same change
