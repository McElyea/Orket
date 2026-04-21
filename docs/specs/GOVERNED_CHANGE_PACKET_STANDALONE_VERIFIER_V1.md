# Governed Change Packet Standalone Verifier v1

Last updated: 2026-04-19
Status: Active contract
Owner: Orket Core

## Purpose

Define the inspection-only verifier for `governed_change_packet.v1`.

This verifier validates packet structure and authority linkage without trusting the full runtime. It does not replace the existing offline claim ladder. It caps packet claims by delegating claim assignment back to the existing offline verifier surface after packet-level checks pass.

## Dependencies

1. `docs/specs/GOVERNED_CHANGE_PACKET_V1.md`
2. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
3. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`

## Admitted Verifier Surface

| Field | Value |
|---|---|
| verifier schema | `governed_change_packet_standalone_verifier.v1` |
| canonical command | `python scripts/proof/verify_governed_change_packet.py --input benchmarks/results/proof/governed_repo_change_packet.json --output benchmarks/results/proof/governed_repo_change_packet_verifier.json` |
| canonical output | `benchmarks/results/proof/governed_repo_change_packet_verifier.json` |
| admitted compare scope | `trusted_repo_config_change_v1` |

## Verdict Surface

The standalone verifier has exactly three packet verdicts:

1. `valid`
2. `invalid`
3. `insufficient_evidence`

These are transport-level packet verdicts only.

## Required Output Diagnostics

The verifier output must include these audit surfaces without adding verdict values:

1. `required_role_diagnostics`: one row for each required packet role, including the observed classification, path, existence flag, digest, schema version, and pass/fail reason.
2. `authority_ref_diagnostics`: one row for each loaded authority ref, including declared stable authority digest, actual stable authority digest, loaded schema version, and load status.
3. `claim_diagnostics`: the requested claim, selected claim tier, whether the requested claim is allowed by the offline claim ladder, and downgrade or rejection reasons.

These diagnostics are explanatory verifier output. They do not create a new proof authority above the authority artifacts they resolve.

## Mapping To The Claim Ladder

GCP-SV-001: `valid` means packet structure, authority linkage, and required evidence refs pass packet-level checks. Claim assignment then proceeds through the existing offline-verifier claim ladder.

GCP-SV-002: `invalid` means the packet is contradictory, tampered, or authority-mismatched. No packet claim is allowed.

GCP-SV-003: `insufficient_evidence` means the packet is structurally coherent enough to inspect but does not carry enough linked authority evidence for the requested packet claim. Lower claims may be preserved only if the existing offline claim ladder permits them.

## Required Packet Checks

The standalone verifier must check at least:

1. packet schema version
2. packet family
3. compare scope
4. operator surface
5. presence of the packet entry disclaimer
6. presence and classification of all required packet roles
7. required authority-ref loadability
8. authority-ref stable digest alignment when a digest is declared
9. witness-bundle verification success
10. offline claim-ladder result for the requested packet claim
11. trusted-kernel conformance pass
12. packet summary alignment with underlying authority artifacts
13. projection-only material not masquerading as authority

## Failure Semantics

The standalone verifier must fail closed as `invalid` when:

1. the packet summary contradicts the underlying authority artifacts
2. required role classifications drift
3. projection-only material is presented as authority
4. packet family, compare scope, or operator surface drifts
5. a declared authority-ref stable digest does not match the current authority-bearing artifact content

The standalone verifier must fail closed as `insufficient_evidence` when:

1. a required packet role is missing
2. a required packet ref does not exist
3. a required packet ref cannot be loaded as a JSON object
4. the requested packet claim is not allowed by the existing offline claim ladder
5. trusted-kernel conformance fails without a direct contradiction

## Non-Interference

The packet verifier must remain inspection-only.

Its current structural proof surface is the canonical trusted-run proof-foundation command:

```text
python scripts/proof/verify_trusted_run_proof_foundation.py
```

That proof must inspect the packet verifier modules in addition to the existing offline verifier modules.
