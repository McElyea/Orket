# Orchestrator turn phase composition

## Summary
- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; bounded Windows source parity below.
- Contract: `docs/specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`.

## Delta
The existing ops entry retains issue validation, epic defaults, initial review
selection and awaited dependency admission. A focused workflow orders the existing
review, preparation and prepared-turn phases through explicit callbacks. Review,
preparation, success, failure, card-completion and provider implementations remain
the owners of their effects. No new coordinator, owner clone or compatibility
forwarder is introduced. Existing public facade calls and signatures remain.

Review construction follows dependency admission. Preparation construction follows
review completion and its stop decision. Success-handler construction follows a
successful dispatch result. These constructors select current coordinator fields
at those original phases; each existing service then retains the same bound
fields/callbacks as before. Existing policy callbacks retain their deferred reads.

Prepared-value normalization remains in the original order before its existing
`try/finally`. Card-completion preparation still precedes the dispatch event and
turn call. Failed turn results select the current failure operation. Provider
close retains its original late function lookup and finally precedence. The
preparation service still captures its own close callback at construction. No
new retry, shielding, cancellation, cleanup or rollback policy is added.

This preserves original stop behavior, approval index, control-plane/card effects,
checkpoint publication, error identity and cleanup boundaries. It does not claim
that loop termination or a successful turn grants accepted build completion.
Existing provider/preparation normalization and borrowed-input debt outside this
cut remain subject to their current contracts.

## Migration Plan
Apply only after the execute-only epic extraction base is accepted. Ops shrinks
from that 577-line base to 478; its remaining 167-line turn function becomes 67.
The new workflow has two functions within 70 lines. The module remains oversized
debt, while all ops functions now meet 70. No existing consumer requires migration:
service constructors and existing ops seams remain composed at their original
owner. The new module receives narrow callbacks, not the coordinator.

Before product application, run the two added phase controls against the accepted
execute-only base, followed by the retained turn/preparation/provider/approval/
control-plane guards and supplied-provider public engine flow. Repeat the exact
selection after application. Preserve constructor/statement AST review, dependency
and typing checks. The new controls use real files/cards/checkpoints and controlled
dispatch/provider boundaries; live inference and installed/Linux proof are separate.

## Rollback Plan
Revert only this turn extraction if phase selection, partial effects, failure or
cleanup parity differs. Keep the earlier epic extraction and its evidence intact.
Retain recorded files/cards/control-plane state before retry: this extraction does
not add rollback authority for successful earlier effects.

## Versioning Decision
Current 0.6.114 candidate, no version bump or capability admission. Existing
public imports and service contracts remain; internal responsibility is narrowed.
Runtime parity is required before acceptance and whole E2 remains open.

## Observed source proof, 2026-09-28

Windows Python 3.11 opening: nine failures and seven passes in 19.16s, with
5,634 unchanged Git-visible inputs. Five input controls expose mutated requests,
API keys, inference/turn deadlines and resolver environment/CWD. Four admission
controls physically show nonempty BLOCKED targets constructing a provider,
posting completion requests and producing successful workload intents. Both turn
phase controls pass on unchanged product. The reports retain each failed case
and actual local HTTP/event/commit readback before assertions.

After the separately reviewed input, admission and turn changes, the combined
Windows Python 3.11 selection passes 364 cases in 221.01s (one upstream warning),
5,638 unchanged inputs. Python 3.12.2 source proof passes 94 cases in 57.89s on
the same 5,638 inputs, including all fourteen workload controls, both turn phase
controls, all 22 tool ownership controls and streaming/provider guards. This is
live local HTTP/file/SQLite and controlled-provider integration proof (primary,
success). Fixture catalog/model bytes do not establish actual model inference.
The Python 3.12 environment name includes installed, but imports are from source;
neither campaign is a fresh installed-artifact acceptance run.

Evidence: `.tmp/goal-20260928-model-turn-opening-v1-*`,
`.tmp/goal-20260928-model-opening-physical-readback.json`,
`.tmp/goal-20260928-model-turn-tool-closing-v1-*`, and
`.tmp/goal-20260928-model-turn-tool-source-py312-v1-*`.
Wider provider/generator/waiter lifetime, canonical quality, installed/Linux and
CAP acceptance remain open. No version bump or whole-lane completion follows.
