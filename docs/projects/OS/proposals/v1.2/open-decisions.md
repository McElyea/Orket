# v1.2 Open Decisions

Last updated: 2026-02-24
Status: Pending decision

## D1. Version Classification
Question:
1. Is this a `kernel_api/v1` tightening or a `kernel_api/v2` break?

Options:
1. `v1` tightening: only additive/tightening changes with compatibility guards.
2. `v2` break: allow shape and meaning changes directly.

Recommendation:
1. Treat as `v2` if `turn-result` decision schema is replaced rather than coexistence.

## D2. Capability Decision Surface
Question:
1. Does `CapabilityDecisionRecord` replace existing `CapabilityDecision` or coexist?

Options:
1. Replace: simpler long-term, higher short-term break risk.
2. Coexist: safer migration, more temporary complexity.

Recommendation:
1. Coexist for one minor cycle, then remove in next major.

## D3. `turn_result_digest` Scope
Question:
1. Which `TurnResult` fields are digest inputs?

Options:
1. Full object.
2. Contract-only object (excluding diagnostics like events/message).

Recommendation:
1. Contract-only digest scope, explicitly documented and test-locked.

## D4. Issue Comparison Ordering
Question:
1. Compare issues by array order or normalized key sort?

Options:
1. Preserve array order.
2. Deterministic key sort (`stage_order`, `location`, `code`, details digest).

Recommendation:
1. Deterministic key sort to avoid host/order noise.

## D5. Registry Digest Input Rule
Question:
1. Registry digest over full wrapper JSON or codes-only payload?

Options:
1. Full wrapper canonical JSON.
2. Codes-only canonical payload.

Recommendation:
1. Full wrapper canonical JSON and lock rule in one place.

## D6. Report ID Input Rule
Question:
1. For `report_id`, should diagnostic fields be nullified or removed?

Options:
1. Set `diagnostic=null`.
2. Remove `diagnostic` keys.

Recommendation:
1. Set `diagnostic=null` for stable canonical shape.
