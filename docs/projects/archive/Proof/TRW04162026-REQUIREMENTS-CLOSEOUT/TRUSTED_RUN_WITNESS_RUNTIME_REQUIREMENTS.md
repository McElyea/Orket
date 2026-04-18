# Trusted Run Witness Runtime Requirements

Last updated: 2026-04-16
Status: Accepted requirements
Owner: Orket Core
Canonical plan: `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/01_TRUSTED_RUN_WITNESS_RUNTIME.md`

## Current Shipped Baseline

Orket already has a partial witness story:

1. target architecture for deterministic runtime authority in `docs/ARCHITECTURE.md`
2. control-plane record families for selected governed paths in `CURRENT_AUTHORITY.md`
3. governed start-path authority in `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
4. determinism claim rules in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
5. minimum auditable record rules in `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
6. ProductFlow governed execution and review package specs in `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md` and `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`

The ProductFlow baseline is intentionally truthful: live governed execution and operator review packaging can succeed, while replay/stability may still report `replay_ready=false`, `stability_status=not_evaluable`, and `claim_tier=non_deterministic_lab_only`.

## Future Delta Proposed By This Doc

Define `Trusted Run Witness v1`: the smallest portable evidence contract that lets Orket say what a bounded governed run proves and what it does not prove.

The first trusted-run witness covers one completed governed run with:

1. one governed input
2. one canonical run identity
3. one bounded approval or operator boundary when the effect requires approval
4. one bounded local effect
5. one deterministic verdict or contract-validation surface
6. one final truth record
7. one verifier-readable witness bundle

## First Slice Decision

The first trusted-run slice MUST extend the existing ProductFlow governed `write_file` path rather than create a new proof fixture.

First slice identity:

1. slice id: `trusted_run_productflow_write_file_v1`
2. source runtime path: ProductFlow governed `write_file` path from `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
3. epic id: `productflow_governed_write_file`
4. issue id: `PF-WRITE-1`
5. governed run id source: the ProductFlow turn-tool `run_id`, not the top-level session id or cards-epic run id
6. bounded local effect: write `agent_output/productflow/approved.txt`
7. deterministic expected content: exact normalized text `approved`
8. terminal issue state: `done`
9. required approval seam: `approval_required_tool:write_file`

This decision intentionally reuses the existing ProductFlow evidence path because it already exercises the approval pause, same-run continuation, checkpoint lineage, effect journal, and final truth surfaces. The implementation target is to turn that bounded path into a trusted-run witness claim, not to widen ProductFlow.

## Claim Surface Decision

The first trusted-run claim surface is:

1. compare scope: `trusted_run_productflow_write_file_v1`
2. primary operator surface: `trusted_run_witness_report.v1`
3. canonical witness bundle root: `runs/<session_id>/trusted_run_witness_bundle.json`
4. canonical verifier proof output: `benchmarks/results/proof/trusted_run_witness_verification.json`
5. target claim tier: `verdict_deterministic`
6. allowed lower-tier fallback: `non_deterministic_lab_only`

The first implementation MUST NOT claim `replay_deterministic` unless it adds replay evidence that satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

The first implementation MUST NOT claim `text_deterministic` unless the accepted compare scope explicitly includes byte identity and the proof records stable output hashes on that same scope.

The `verdict_deterministic` target requires at least two equivalent executions or an explicit campaign artifact showing stable deterministic verdict and stable must-catch outcomes for the ProductFlow trusted-run slice. A single-run witness may be useful but MUST remain `non_deterministic_lab_only`.

## What This Doc Does Not Reopen

1. It does not reopen ControlPlane as a broad lane.
2. It does not require universal control-plane coverage.
3. It does not promote every current runtime path into trusted-run status.
4. It does not claim model-generated content is correct.
5. It does not claim byte-identical text determinism.
6. It does not implement the full offline verifier; that belongs to a later implementation plan or companion lane.
7. It does not create public publication authority.

## Required Terms

`trusted_run`
1. a bounded governed run whose witness bundle satisfies this requirements draft

`witness_bundle`
1. portable evidence package for one trusted run
2. evidence contract, not a success claim by itself

`claim_tier`
1. one of the claim tiers defined in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

`compare_scope`
1. bounded domain on which the trusted-run claim is asserted

`operator_surface`
1. concrete report or artifact surface used to evaluate the claim

## Scope Requirements

TRW-REQ-001: The first trusted-run slice compare scope MUST be `trusted_run_productflow_write_file_v1`.

TRW-REQ-002: The first trusted-run slice primary operator surface MUST be `trusted_run_witness_report.v1`.

TRW-REQ-003: The first trusted-run slice MUST target a bounded local mutation or state effect, not broad orchestration.

TRW-REQ-004: The first trusted-run slice MUST preserve the distinction between runtime authority records, review-package projections, and human-facing summaries.

TRW-REQ-005: The first trusted-run slice MUST NOT require all Orket run surfaces to emit trusted-run bundles.

TRW-REQ-006: The first trusted-run slice MUST extend the ProductFlow governed `write_file` path and MUST NOT introduce a second ProductFlow golden path.

TRW-REQ-007: The first trusted-run slice MUST keep the ProductFlow governed turn-tool `run_id` as canonical identity.

## Bundle Identity Requirements

TRW-REQ-010: A witness bundle MUST carry a stable `schema_version`.

TRW-REQ-011: A witness bundle MUST carry a non-empty `bundle_id`.

TRW-REQ-012: A witness bundle MUST carry the canonical governed `run_id`.

TRW-REQ-013: A witness bundle MAY carry a `session_id` or artifact-root locator, but that locator MUST NOT substitute for the canonical governed `run_id`.

TRW-REQ-014: A witness bundle MUST carry `compare_scope`, `operator_surface`, `claim_tier`, `policy_digest`, and `control_bundle_ref` or equivalent control-bundle digest.

TRW-REQ-015: A witness bundle MUST identify every included artifact by path plus digest or by durable record id plus digest-equivalent integrity reference.

TRW-REQ-016: The first trusted-run witness bundle MUST be rooted at `runs/<session_id>/trusted_run_witness_bundle.json` unless a same-change durable spec extraction selects a different canonical path.

TRW-REQ-017: The first trusted-run verifier proof output MUST be rooted at `benchmarks/results/proof/trusted_run_witness_verification.json` and MUST use the repository diff-ledger writer convention.

## Required Authority Matrix

The first trusted-run witness MUST treat these surfaces as required authority:

| Evidence family | Required source | Purpose | Failure semantics |
|---|---|---|---|
| governed input | ProductFlow canonical run input or manifest evidence | proves what work was admitted | missing or drifted input blocks trusted-run verification |
| policy snapshot | resolved policy snapshot for the governed run | proves governing policy digest | missing or digest drift blocks trusted-run verification |
| configuration snapshot | resolved configuration snapshot for the governed run | proves governing configuration digest | missing or digest drift blocks trusted-run verification |
| run authority | governed turn-tool `RunRecord` | proves canonical run identity | missing or mismatched `run_id` blocks trusted-run verification |
| attempt authority | current governed turn-tool `AttemptRecord` | proves attempt lineage | missing or mismatched attempt blocks trusted-run verification |
| step authority | governed turn-tool step records | proves runtime path | missing or mismatched step blocks trusted-run verification |
| approval request | `approval_required_tool:write_file` request | proves operator gate request | missing approval request blocks trusted-run verification |
| operator action | approval resolution or operator action record | proves approval or denial decision | missing resolution blocks trusted-run verification |
| checkpoint authority | checkpoint and acceptance evidence for continuation | proves same-run continuation basis | missing or drifted checkpoint blocks trusted-run verification |
| reservation and lease | namespace/resource reservation and lease records | proves governed ownership | missing or contradictory authority blocks success claims |
| effect journal | effect-journal entries for `write_file` and required status mutation | proves observed effect lineage | missing or contradicted effect blocks success claims |
| deterministic verdict | `trusted_run_contract_verdict.v1` or explicit blocker | proves contract result on compare scope | missing verdict keeps claim below `verdict_deterministic` |
| final truth | target-side `FinalTruthRecord` | proves terminal truth classification | missing final truth blocks success claims |

The first trusted-run witness MAY include these supporting surfaces:

1. ProductFlow review index
2. run evidence graph JSON, Mermaid, or HTML views
3. packet-1 and packet-2 projections
4. replay review truthful blocker
5. human-facing summary text

Supporting surfaces MUST NOT replace the required authority sources above.

Forbidden substitutes:

1. `session_id` MUST NOT substitute for governed `run_id`.
2. `run_summary.control_plane.run_id` MUST NOT substitute for the governed turn-tool `run_id`.
3. logs MUST NOT substitute for effect-journal evidence.
4. narrated output MUST NOT substitute for deterministic verdict or observed effect evidence.
5. ProductFlow review package success MUST NOT substitute for trusted-run witness verification.

## Authority Lineage Requirements

TRW-REQ-020: A trusted-run witness MUST include or reference the governed input that was admitted.

TRW-REQ-021: A trusted-run witness MUST include or reference the resolved policy snapshot used by the run.

TRW-REQ-022: A trusted-run witness MUST include or reference the resolved configuration snapshot used by the run.

TRW-REQ-023: A trusted-run witness MUST include the canonical run, attempt, and step authority needed to explain the admitted execution path.

TRW-REQ-024: A trusted-run witness MUST fail verification when run, attempt, step, checkpoint, effect, or final-truth identifiers drift across bundle surfaces.

TRW-REQ-025: Review indexes, summaries, graphs, or other convenience surfaces MUST be marked or treated as projections unless a durable source spec explicitly makes them authority.

## Approval And Continuation Requirements

TRW-REQ-030: If the trusted-run effect requires approval, the witness MUST include the approval request evidence.

TRW-REQ-031: If the trusted-run effect requires approval, the witness MUST include the operator action or approval resolution evidence.

TRW-REQ-032: Approval continuation evidence MUST bind the approval decision to the same governed run.

TRW-REQ-033: Approval continuation evidence MUST bind the continuation to the accepted checkpoint used for the same governed run.

TRW-REQ-034: Approval denial MUST produce terminal-stop or blocked truth; it MUST NOT silently disappear from the witness.

TRW-REQ-035: Unsupported or ambiguous approval lifecycle states MUST fail closed for trusted-run verification.

## Resource And Effect Requirements

TRW-REQ-040: A trusted-run witness MUST include resource reservation and lease evidence when the effect is namespace-scoped or resource-owned.

TRW-REQ-041: A trusted-run witness MUST include effect-journal evidence for every in-scope observed effect.

TRW-REQ-042: An effect journal entry MUST identify its run, attempt, step, authorization basis, intended target, observed result when available, and uncertainty classification.

TRW-REQ-043: A success claim MUST NOT be allowed when the in-scope effect is missing, contradicted, or only narrated.

TRW-REQ-044: A trusted-run witness MUST preserve absence truth for missing effects, missing observations, missing verifier outputs, and missing contract verdicts.

## Verdict And Final Truth Requirements

TRW-REQ-050: A trusted-run witness MUST include `trusted_run_contract_verdict.v1` or an explicit truthful blocker for the first slice.

TRW-REQ-051: A trusted-run witness MUST include a final truth record or explicit truthful blocker.

TRW-REQ-052: A final truth `success` result MUST require sufficient evidence under the applicable source contract.

TRW-REQ-053: A final truth result MUST remain separate from replay readiness and stability status.

TRW-REQ-054: A model-assisted critique MAY appear as advisory evidence, but it MUST NOT replace deterministic verdict authority for mechanically checkable first-slice requirements.

TRW-REQ-055: The first deterministic verdict MUST verify exact output path, exact normalized output content, expected terminal issue status, final-truth success classification, and absence of trusted-run-scope missing evidence.

TRW-REQ-056: The first deterministic verdict MUST expose stable must-catch outcomes for at least missing output artifact, wrong output content, missing approval resolution, missing effect evidence, missing final truth, and canonical run-id drift.

## Claim-Tier Requirements

TRW-REQ-060: A trusted-run witness MUST state the lowest truthful claim tier supported by its evidence.

TRW-REQ-061: A witness with no comparative replay, repeat, or verdict-stability evidence MUST NOT claim `replay_deterministic`, `verdict_deterministic`, or `text_deterministic`.

TRW-REQ-062: `text_deterministic` MUST NOT be claimed unless byte identity or output hash identity is explicitly in scope and proven.

TRW-REQ-063: The human-facing result MUST NOT use broader wording than the witness `claim_tier` and `compare_scope` allow.

TRW-REQ-064: The first implementation MUST target `verdict_deterministic` through repeat or campaign evidence over `trusted_run_productflow_write_file_v1`.

TRW-REQ-065: If the repeat or campaign evidence is absent, partial, or blocked, the first implementation MUST report `non_deterministic_lab_only`.

## Portability And Safety Requirements

TRW-REQ-070: A witness bundle MUST be inspectable without requiring live model access.

TRW-REQ-071: A witness bundle MUST be inspectable without rerunning the workflow.

TRW-REQ-072: A witness bundle MUST NOT include secrets, tokens, or credentials.

TRW-REQ-073: Paths inside the bundle MUST be workspace-relative or bundle-relative unless a source contract explicitly requires an absolute local path.

TRW-REQ-074: Verification over the bundle MUST be side-effect free.

## Negative Verification Requirements

TRW-REQ-080: Corrupting the canonical `run_id` in one required authority surface MUST cause verification failure.

TRW-REQ-081: Removing the final truth record from a bundle that claims success MUST cause verification failure.

TRW-REQ-082: Removing the deterministic verdict or explicit truthful blocker MUST cause verification failure.

TRW-REQ-083: Removing approval resolution evidence from an approval-required slice MUST cause verification failure.

TRW-REQ-084: Removing or contradicting effect evidence from a success-claiming slice MUST cause verification failure.

TRW-REQ-085: Removing claim-tier or compare-scope fields MUST cause verification failure.

TRW-REQ-086: Mutating expected output content away from `approved` MUST cause deterministic verdict failure.

TRW-REQ-087: Mutating the ProductFlow trusted-run `session_id` locator without preserving the governed run resolver witness MUST cause verification failure.

## Spec Extraction Requirements

TRW-REQ-090: Before implementation begins, durable contract material from this requirements draft MUST be extracted into `docs/specs/TRUSTED_RUN_WITNESS_V1.md`.

TRW-REQ-091: The extracted spec MUST define the witness bundle schema, required authority matrix, claim surface, and negative verification expectations for `trusted_run_productflow_write_file_v1`.

TRW-REQ-092: The implementation plan MUST point to `docs/specs/TRUSTED_RUN_WITNESS_V1.md` instead of treating this active requirements draft as durable runtime contract authority.

TRW-REQ-093: `CURRENT_AUTHORITY.md` MUST be updated only when implementation changes actual behavior or source-of-truth paths.

## Acceptance Proof

Before this requirements draft can close as implemented, the adopted lane must provide:

1. contract or integration proof for witness-bundle schema validation
2. contract or integration proof for authority-lineage id alignment
3. negative corruption tests for required evidence families
4. a side-effect-free verification proof over at least one bundle
5. at least two equivalent ProductFlow trusted-run executions or a campaign artifact proving stable deterministic verdict for the selected first trusted-run slice, unless live execution is blocked and reported as such
6. one verifier proof output at `benchmarks/results/proof/trusted_run_witness_verification.json`

Proof reports must record:

1. proof type: live, contract, integration, structural, or absent
2. observed path: `primary`, `fallback`, `degraded`, or `blocked`
3. observed result: `success`, `failure`, `partial success`, or `environment blocker`
4. claim tier
5. compare scope
6. operator surface
7. remaining blockers or drift

## Resolved Decisions

1. `Trusted Run Witness v1` must be extracted into `docs/specs/TRUSTED_RUN_WITNESS_V1.md` before implementation.
2. The first trusted-run slice extends ProductFlow.
3. The first deterministic verdict is a small combined verdict over exact artifact path, normalized content, issue status, final truth, required control-plane lineage, and trusted-run-scope missing evidence.
4. The first implementation must include enough side-effect-free verification to produce `trusted_run_witness_report.v1`; broader offline verifier product work may remain future work.
5. The first witness bundle root is `runs/<session_id>/trusted_run_witness_bundle.json`.
6. The first verifier proof output is `benchmarks/results/proof/trusted_run_witness_verification.json`.

## Remaining Implementation Decisions

1. exact JSON field names for `trusted_run_witness_bundle.json`
2. exact JSON field names for `trusted_run_contract_verdict.v1`
3. exact corruption-fixture file layout
4. exact helper or script names for bundle build and verification
5. whether repeat evidence is collected by rerunning the existing ProductFlow script twice or by a dedicated trusted-run campaign script

## Requirements Readiness

The requirements were accepted by explicit Priority Now completion request on 2026-04-16.

They are not implementation authority until the user explicitly asks for implementation. Implementation must first extract durable contract material into `docs/specs/TRUSTED_RUN_WITNESS_V1.md`.
