# v1.2 Migration Matrix (Proposal)

Last updated: 2026-02-24
Status: Draft proposal (non-authoritative)

## Mapping

| Current Artifact | Proposed Artifact | Change Type | Break Risk | Required Tests/Gates | Notes |
|---|---|---|---|---|---|
| `contracts/capability-decision.schema.json` | `contracts/capability-decision-record.schema.json` (new) | Add in parallel | Medium | validator schema contracts, capability scenario tests, replay parity tests | Locked: coexist one minor cycle, then replace in later major. |
| `contracts/replay-report.schema.json` | tightened replay report schema | Tighten existing | Medium | schema contracts, replay vectors, API compare schema tests | Must preserve v1 semantics; use additive fields if needed. |
| none | `contracts/replay-bundle.schema.json` | Additive | Low/Medium | bundle validation tests, comparator input tests | New manifest contract for replay input. |
| none | `contracts/stage-order-v1.json` | Additive | Low | ordering tests, comparator mismatch ordering tests | Becomes authoritative stage spine. |
| `contracts/turn-result.schema.json` | add parallel decision-record location/ref | Modify existing (additive) | Medium | turn-result schema tests, runtime emission tests | Locked: no semantic swap of existing field meaning under v1 tightening. |
| `contracts/error-codes-v1.json` | add v1.2 codes | Additive | Low | `scripts/audit_registry.py`, registry tests | No rename/removal allowed in v1. |
| comparator implementation behavior | canonical parity and report-id derivation laws | Tighten behavior | Medium | replay vector tests, 100-iteration stability, API compare tests | Locked: IssueKey ordering + multiplicity, nullification-over-omission. |
| registry digest rule (implicit) | explicit canonical digest rule | Clarification | Low/Medium | registry lock tests, replay lock mismatch tests | Locked: full wrapper canonical JSON digest. |

## Risk Classification Guidance
1. `Low`: additive + no existing contract interpretation change.
2. `Medium`: behavior tightening that may alter outcomes without schema breaks.
3. `High`: schema/meaning changes likely to break existing consumers.

## Suggested Rollout Strategy
1. Land additive artifacts first (stage-order, replay-bundle, codes).
2. Land comparator/law tightening behind strict tests.
3. Resolve decision-record coexist/replace.
4. Only then update authoritative contract index and runtime schemas.
