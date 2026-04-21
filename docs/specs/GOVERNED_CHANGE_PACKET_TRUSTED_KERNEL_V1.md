# Governed Change Packet Trusted Kernel v1

Last updated: 2026-04-19
Status: Active contract
Owner: Orket Core

## Purpose

Define the bounded trusted-kernel claim for the first Governed Change Packet.

This contract does not prove the whole runtime. It defines the smallest kernel Orket currently claims for `trusted_repo_config_change_v1` and the machine-checkable model surface used to fail closed on impossible packet stories.

## Dependencies

1. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

## Admitted Boundary

This kernel contract is admitted only for:

| Surface | Value |
|---|---|
| compare scope | `trusted_repo_config_change_v1` |
| operator surface | `trusted_run_witness_report.v1` |
| model surface | `bounded_python_state_machine` |
| canonical model command | `python scripts/proof/verify_governed_change_packet_trusted_kernel.py` |
| canonical model output | `benchmarks/results/proof/governed_change_packet_trusted_kernel_model.json` |

The kernel claim stops at one bounded local repo config mutation and the inspection-only verifier path over its packet artifacts.

## Frozen Kernel Obligations

The Governed Change Packet kernel is exactly these ten obligations:

| Obligation | Meaning | Required evidence family |
|---|---|---|
| `GCP-KER-001` | governed input identity | persisted flow request |
| `GCP-KER-002` | resolved policy and configuration identity | policy digest plus snapshot refs |
| `GCP-KER-003` | approval binding | approval request plus approving operator action |
| `GCP-KER-004` | reservation and lease authority | reservation and lease lineage on the bounded target |
| `GCP-KER-005` | checkpoint acceptance before effect | accepted pre-effect checkpoint |
| `GCP-KER-006` | effect publication and lineage | effect journal plus observed output artifact |
| `GCP-KER-007` | deterministic validator result | `trusted_repo_config_validator.v1` pass result |
| `GCP-KER-008` | final-truth publication and uniqueness | aligned `final_truth_record_id` and successful final truth |
| `GCP-KER-009` | witness-bundle completeness for the bounded claim | live proof, witness bundle, campaign report, and offline verifier report align |
| `GCP-KER-010` | verifier non-interference | trusted-kernel model pass plus side-effect-free verifier evidence |

Any missing or contradictory obligation fails the packet claim.

## Machine-Checked Safety Properties

The bounded model must mechanically check:

1. no effect without accepted authority
2. no successful final truth without validator and effect evidence
3. no contradictory final truth
4. no lease reuse after invalidation
5. verifier path is inspection-only

The model MAY reject transitions before they become reachable state. Rejected transitions count as fail-closed behavior, not as kernel failures.

## Canonical Conformance Surface

The packet must carry a conformance projection over the admitted authority artifacts in:

```text
packet.trusted_kernel.conformance
```

That conformance projection is an operator entry projection only. It must resolve back to the underlying authority refs and the canonical model output rather than acting as independent authority.

The canonical conformance result surface is:

| Field | Value |
|---|---|
| schema version | `governed_change_packet_trusted_kernel_conformance.v1` |
| result values | `pass` or `fail` |
| required row ids | `GCP-KER-001` through `GCP-KER-010` |

## Failure Semantics

The kernel must fail closed when:

1. the governed input drifts from `TRUSTED-CHANGE-1`
2. policy or configuration identity is missing
3. approval does not bind the bounded target
4. reservation or lease evidence is missing
5. effect publication is missing or contradicted
6. validation is missing or failing
7. final truth is missing or contradictory
8. the packet claims a stronger bounded story than the witness and offline evidence allow
9. verifier non-interference is not mechanically supported

## Limits

This contract does not prove:

1. the whole Python runtime
2. general workflow determinism
3. replay determinism
4. text determinism
5. provider-backed workflow slices
