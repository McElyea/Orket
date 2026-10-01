# Explicit pipeline registry settings

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented after 0.6.114; scoped Windows source closing passed.
- Contract: `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.

## Delta

Direct pipeline construction accepted explicit construction settings but built
its decision registries from the caller's bound or persistent settings. This
could select a different strategy, ignore a retired-setting refusal, or reject
an explicitly empty selection because of unrelated ambient settings.

The existing builder now accepts explicit `user_settings`. Pipeline construction
and both subordinate wiring paths supply their selected settings. Orchestrator
detaches the optional mapping on entry and forwards it at its existing selection
point. Omission retains bootstrap behavior. The three registries remain distinct;
no caller context is rebound and no omitted preferences are loaded. Environment
precedence and organization policy remain unchanged.

## Migration Plan

No mandatory caller-signature migration or compatibility shim is introduced.
Embeddings with selected settings should pass the explicit builder/Orchestrator
keyword. The standard pipeline does so. Standalone runtime-context composition
also forwards its supplied construction settings; ConfigLoader forwards its
already serialized settings when it creates its own registry. Omission and
explicit registry precedence remain unchanged. Arbitrary custom factories are
not certified by these two call-site corrections.

The first opening's two healthy controls incorrectly manufactured an empty SQLite
database and demanded eagerly created tables. V2 observes the actual initialized
store binding and absent lazy database. Its real source opening is six failures
and two passes, recorded in
`.tmp/goal-20260928-registry-settings-opening-v2-readback.json`. Selection mismatch,
retired selected settings and ambient contamination are the six counterexamples.
Closing must retain independent registry identities, caller snapshots, file bytes,
runtime cleanup, preference omission and existing constructor/selection guards.

The additional standalone opening observed nine failures and five passes through
real context/ConfigLoader construction. It retained the same selection, empty and
retired-setting counterexamples, plus omission, supplied-registry precedence and
post-construction dictionary mutation controls. Receipt:
`.tmp/goal-20260928-sdk-observation-standalone-opening-v1-readback.json`.

## Observed source closing

Windows Python 3.11 source closing passes all **464** selected cases in 207.12s,
with **5,605 unchanged Git-visible inputs** and one upstream Starlette warning.
The earlier combined closing passed 410 cases in 170.25s with 5,600 unchanged
inputs. The expanded run retains those cases and adds the SDK observed-publication,
standalone settings and existing construction guards. Evidence:
`.tmp/goal-20260928-captured-inputs-closing-v4-{inputs,readback}.json` and sibling
XML/log; earlier `.tmp/goal-20260928-input-composition-closing-v3-*`.
Proof is live local native/files/SQLite/child and loopback HTTP behavior with
declared supplied-model controls, path primary, result success. No actual model
provider, remote Gitea, current installed wheel or Linux proof is implied.

## Rollback Plan

On a selection or constructor regression, restore the six product deltas together
and retain the failed observations. This change performs no settings rewrite or
store migration; do not mutate persisted configuration to mask a failed handoff.

## Versioning Decision

Unpublished change after 0.6.114; no version bump. This is source composition scope,
not executed-tool, provider, installed-platform or complete D2 acceptance.
