# v1.2 Migration Matrix (Proposal)

Last updated: 2026-02-24
Status: Draft proposal (non-authoritative)

## Mapping

| Current Artifact | Proposed Artifact | Change Type | Break Risk | Required Tests/Gates | Notes |
|---|---|---|---|---|---|
| `contracts/capability-decision.schema.json` | `contracts/capability-decision-record.schema.json` (new) | Add or replace | Medium/High | validator schema contracts, capability scenario tests, replay parity tests | Replacement vs coexistence is unresolved. |
| `contracts/replay-report.schema.json` | tightened replay report schema | Tighten existing | High | schema contracts, replay vectors, API compare schema tests | Could require major bump if shape/meaning changes. |
| none | `contracts/replay-bundle.schema.json` | Additive | Low/Medium | bundle validation tests, comparator input tests | New manifest contract for replay input. |
| none | `contracts/stage-order-v1.json` | Additive | Low | ordering tests, comparator mismatch ordering tests | Becomes authoritative stage spine. |
| `contracts/turn-result.schema.json` | decisions ref to decision-record schema | Modify existing | High | turn-result schema tests, runtime emission tests | Potential v2 break if existing consumers depend on current shape. |
| `contracts/error-codes-v1.json` | add v1.2 codes | Additive | Low | `scripts/audit_registry.py`, registry tests | No rename/removal allowed in v1. |
| comparator implementation behavior | canonical parity and report-id derivation laws | Tighten behavior | Medium | replay vector tests, 100-iteration stability, API compare tests | Must lock digest input/exclusion rules. |
| registry digest rule (implicit) | explicit canonical digest rule | Clarification | Medium | registry lock tests, replay lock mismatch tests | Must define exact digest payload scope. |

## Risk Classification Guidance
1. `Low`: additive + no existing contract interpretation change.
2. `Medium`: behavior tightening that may alter outcomes without schema breaks.
3. `High`: schema/meaning changes likely to break existing consumers.

## Suggested Rollout Strategy
1. Land additive artifacts first (stage-order, replay-bundle, codes).
2. Land comparator/law tightening behind strict tests.
3. Resolve decision-record coexist/replace.
4. Only then update authoritative contract index and runtime schemas.
