# Orchestrator policy and transition ownership

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source closing passed.
- Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.
- Scope: focused runtime/prompt/protocol policy, real coordinator transition and
  verification bodies, canonical support construction and affected consumers.

## Delta

The prior facade forwarded private policy methods into a 1,586-line operations
module and exposed support classes/settings solely for compatibility hooks.
Support construction caught any internal `TypeError` and retried with fewer inputs.
The constructor opening observed two invocations for each of the four affected
real constructors: **4 failures, 8 passes**, with all 5,539 inputs unchanged.

Policy selection now consumes explicit values at the same phase/callback and in
the same settings/organization order. No eager execution snapshot is introduced.
The coordinator owns actual card persistence, local transition and ordered issue/
scheduler publication, plus its public verification body. Support construction
uses canonical implementations once and preserves their original errors.
The facade retires 26 policy forwarders, class/error/settings compatibility exports
and getter chains. Existing mutable run/transcript/lock state remains with its owner.
New imports use grouped runtime package authority, preserving external flat aliases.

The operations file shrinks to 947 lines and the coordinator is 365; four focused
modules are below 120 lines. The remaining execute/replan/turn bodies still exceed
size limits. This scoped extraction does not close E2, ambient settings ownership,
the execute return-annotation discrepancy or repository-wide architecture debt.

## Migration Plan

1. Direct support construction takes no class-getter hooks. Patch canonical support
   construction imports or class methods in tests; supplied constructors accept the
   actual selected keyword inputs. No shim or alternate retry path is added.
2. Direct policy consumers call their focused service functions. Six existing test
   consumers migrate; their 82 retained definitions preserve parameters/markers and
   all 326 assertions after explicit selector migration. The obsolete
   `test_orchestrator_helper_methods_are_explicit_class_members` is deliberately
   retired because its two assertions required the removed forwarding design.
3. Both Quality jobs retain constructor, verification and transition controls.
   Closing acceptance must retain the existing public engine/run-card path with
   supplied provider, real tools/files/card receipts and provider cleanup.

## Verification

Before application the existing 28-selector selection passed **227 tests** in
79.42s, exit 0, all 5,539 inputs unchanged. The separate constructor opening is
contract proof using actual constructors with a controlled selected-profile
conversion failure. The source baseline mixes real local integration and declared
unit/contract fixtures; it is not external-provider or live Docker proof.

Structural review retains provider try/finally, remaining operation bodies after
declared call substitutions, public verification/execute ASTs and publication
ordering. Original and grouped-import correction receipts remain separate in
`.tmp/e2-orchestrator-review-20260928/`. Closing passed **268 tests** in 78.64s,
exit 0, with all 5,544 inputs unchanged. Exact comparison retains 226 baseline
identities, retires the one obsolete forwarder assertion, and adds 12 constructor
plus 30 workflow controls. Public supplied-provider engine/run-card, real tools,
retained completion/transition state and owned provider cleanup pass in that set.
Canonical scoped Ruff passes. Path: primary; result: success. Evidence prefixes:
`.tmp/goal-20260928-orchestrator-policy-{before,after}-v1-`, separate
`orchestrator-construction-opening-v1-`, and `orchestrator-policy-parity.json`.
The supplied-provider case is local integration, not external model acceptance.

## Rollback Plan

A changed policy selection, transition/publication order or resource lifetime
blocks acceptance. Retain its failing evidence; restore code and affected consumers
together if necessary. Do not reintroduce constructor retries silently or erase
durable state after failed publication. This change has no storage migration.

## Versioning Decision

Unreleased 0.6.114 source candidate; no release/version change. Public coordinator
constructor, execute and verification entrypoints retain behavior except removal
of the unsafe support-constructor retry. Retired private forwarding/hooks require
direct consumers to use their actual owners. Full installed/platform and quality
acceptance remains in the architectural-truth plan.
