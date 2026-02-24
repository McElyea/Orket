# Go/No-Go Decision: Modularity Refactor Timing

Date: 2026-02-24

## Direct Answer

1. Is this the right time to refactor again?
- Yes, but only for staged stabilization-first refactor (`MR-1`) followed by modular seams (`MR-2`).
- No for broad rewrite refactor right now.

2. Are things likely to break soon anyway?
- Yes, there is credible near-term break risk from known defects and weak guardrails.

3. Are we preventing the break so concern is null?
- Not null.
- We can materially reduce break risk with `MR-1`, then keep reducing with `MR-2` and `MR-3`.
- Risk does not become zero; it becomes managed and visible.

## Why This Decision

1. Known critical runtime defects exist in logging isolation, metrics return, and webhook status typing.
2. Multiple architecture guard tests currently allow false confidence due path-root defects.
3. Dependency enforcement has blind spots (`root` classification), so unmanaged drift can continue.

## Decision Rule

Proceed if:
1. `MR-1` is executed first and passes acceptance criteria.
2. `MR-2` starts only after `MR-1` closes critical defects.
3. `MR-3` starts once module seams are in place and policy is agreed.

Pause if:
1. `MR-1` cannot be made green without repeated regressions.
2. Boundary policy remains unresolved (especially `application -> adapters`).

## Confidence Statement

1. Doing nothing has higher break risk than staged refactor.
2. Doing staged refactor now is the most stable forward path.
3. Concern is valid and should drive gating, not halt work.

