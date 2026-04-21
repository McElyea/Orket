# Governed Change Packet v1

Last updated: 2026-04-19
Status: Active contract
Owner: Orket Core

## Purpose

Define the first Governed Change Packet surface for outside-operator inspection.

The first admitted packet is the governed repo-change packet for `trusted_repo_config_change_v1`. It is the primary operator entry artifact for that slice, but it is not a substitute authority surface.

## Dependencies

1. `docs/specs/GOVERNED_CHANGE_PACKET_TRUSTED_KERNEL_V1.md`
2. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
3. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
4. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

## Admitted Packet Surface

| Field | Value |
|---|---|
| packet schema | `governed_change_packet.v1` |
| packet family | `governed_repo_change_packet_v1` |
| compare scope | `trusted_repo_config_change_v1` |
| operator surface | `trusted_run_witness_report.v1` |
| canonical packet command | `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_governed_repo_change_packet.py` |
| canonical packet output | `benchmarks/results/proof/governed_repo_change_packet.json` |

The packet is admitted only for the bounded local repo config mutation over `repo/config/trusted-change.json`.

## Packet Role

GCP-V1-001: The packet MAY be the primary operator artifact for this slice.

GCP-V1-002: The packet MUST remain an entry surface over authority-bearing artifacts rather than a substitute authority surface.

GCP-V1-003: Any claim-bearing packet check MUST resolve to the underlying authority artifacts or verifier outputs named in the packet manifest.

## Canonical Packet Artifacts

The packet manifest must carry these required roles:

| Role | Classification | Required | Purpose |
|---|---|---|---|
| `approved_live_proof` | `authority_bearing` | yes | bounded live execution result |
| `flow_request` | `authority_bearing` | yes | governed input identity |
| `run_authority` | `primary_authority` | yes | approval, reservation, checkpoint, effect, and final truth lineage |
| `validator_report` | `authority_bearing` | yes | deterministic validator result |
| `witness_bundle` | `primary_authority` | yes | primary bundle authority |
| `campaign_report` | `authority_bearing` | yes | repeated evidence stability |
| `offline_verifier_report` | `authority_bearing` | yes | claim-ladder ceiling |
| `trusted_kernel_model_check` | `authority_bearing` | yes | bounded kernel model result |

The packet may also carry:

1. negative proof refs classified as `negative_proof`
2. exactly one `operator_summary` row classified as `entry_projection`

## Embedded Packet Sections

The packet must include:

1. packet identity and admitted compare scope
2. a primary operator summary
3. a claim summary
4. an artifact manifest
5. a trusted-kernel section with:
   - model-check result
   - conformance projection
6. explicit limitations

The primary operator summary and limitations are support projections only. They must not outrank the underlying authority artifacts.

## Packet Claim Rules

The packet may state only the current truthful claim ceiling that the underlying offline verifier allows.

For the first packet:

1. the requested packet claim is `verdict_deterministic`
2. the current truthful claim ceiling may be at most `verdict_deterministic`
3. replay determinism remains unproven
4. text determinism remains unproven
5. the slice remains fixture-bounded

## Required Limits

The packet must not claim:

1. arbitrary repo changes are covered
2. the whole runtime is mathematically proven
3. replay determinism
4. text determinism
5. that packet projections alone are proof authority

## Negative Proof Family

The current packet family must ship or reference at least:

1. one denial negative proof
2. one validator-failure negative proof

Those negative proofs may support evaluator understanding, but they do not replace the required positive authority artifacts above.
