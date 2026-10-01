# Nested shared I/O fatal failure ownership

## Summary
- Change title: settle fatal failures through enclosing shared I/O operation tasks.
- Owner: shared I/O adapter boundary.
- Date: 2026-09-28.
- Affected contract: `docs/specs/SHARED_IO_CANCELLATION.md`.
- Status: implemented; scoped Windows CPython 3.11/3.12 source closing passes.

## Delta
- Previous behavior: the native leaf converts `SystemExit` and `KeyboardInterrupt`
  to a settled result, then raises the selected object to its caller. Source
  tracing and twelve isolated opening failures show an enclosing shared owner's
  operation Task exposes the fatal failure to asyncio before public settlement.
- Implemented behavior: adapt the admitted coroutine's `send`/`throw` protocol at
  the existing task boundary, contain only those two fatal failures as exact
  result objects, and retain the existing settlement/precedence logic. Remove
  the now-redundant leaf-only conversion. Factory timing, rejected values,
  caller ownership of refused unstarted work, and cancellation identity stay.
- Why now: nested ownership is required by the proposed card acceptance capture
  operation; leaf-only native ownership cannot yet support its failure claim.
- Visible limit: custom task factories see an adapter instead of the original
  coroutine. Exact coroutine identity, concrete-type-sensitive custom task
  factories, and custom coroutine introspection are outside preservation claims.
  Python 3.12 eager task factory behavior is unverified; the default-Task
  controls do not establish its compatibility.

## Migration Plan
1. Compatibility window: no alias, fallback, or second owner is introduced.
2. Apply only the isolated test/helper controls first. Run the twelve unchanged
   source children before any product change. Record exit, failure, cleanup and
   immutable input hashes. A static prediction is not an observed opening.
3. After review of the opening, apply the single-owner change and contract update.
4. Run all 34 proposed controls plus existing cancellation identity, diagnostic
   refusal, native fatal publication, and native diagnostic ownership controls.
   Repeat applicable gates with the supported CPython 3.11/3.12 installed
   candidates; review coroutine admission and source/package origins explicitly.

## Rollback Plan
1. Trigger: admission timing, accepted coroutine behavior, cancellation identity,
   refusal ownership or exception graph regresses.
2. Restore the prior shared owner; retain the failed controls and leave nested
   card/epic ownership unapplied until a verified correction exists.
3. Native writes can precede failure. No rollback, atomicity, retry or recovery
   authority is added, and fixture emergency cleanup is not product proof.

## Versioning Decision
- Version bump type: fix under the architectural-truth lane, subject to owner review.
- Effective version/date: dirty candidate after 0.6.114, 2026-09-28; no version,
  commit or tag change.
- Downstream impact: default asyncio Task handling of admitted coroutine fatal
  failures becomes retainable at nested public callers. Uncaught public fatal
  failures retain their ordinary meaning. These bounded controls do not prove
  every async owner, event-loop implementation or custom task factory.

## Observed opening

Windows Python 3.11.14 executes 12 failed and 22 passed in 10.83 seconds, exit 1,
with all 5,530 Git-visible inputs unchanged. All twelve nested fatal children exit
through their real fatal status after native settlement, without reaching the
required successful public-caller observation. The parent reaps every child
without emergency kill. All coroutine admission/protocol and closed-executor
refusal controls pass unchanged product. Evidence:
`.tmp/goal-20260928-nested-fatal-opening-v1-{inputs,readback}.json`, XML and log.
This is an observed local native opening, not installed or provider acceptance.

## Closing evidence and fixture correction

The initial 119-case closing passes on Python 3.11.14. Python 3.12.2 passes 113
cases but rejects both generator forms at the test's direct `create_task` call,
before invoking the shared owner. The test had incorrectly assumed identical
generator admission across interpreters. Its correction uses the actual selected
interpreter's direct Task admission as the oracle: when refused, the same unstarted
generator must receive the same refusal arguments from the shared owner, remain
unconsumed, and be closed by its caller. Admitted cases still prove execution,
ordinary failure and cancellation identity. There is no product version branch,
skip or admission fallback. Original results remain unchanged.

Corrected closing runs retain all 119 identities and pass on both interpreters:
27.75s on 3.11 and 33.76s on 3.12, with 5,531 source inputs unchanged during each
run. Both execute all twelve fatal children, preserving exact failure/cause/context,
partial SQLite state, owned closure and healthy subsequent operations; every child
is reaped without emergency kill. Existing cancellation/diagnostic/API publication
and cleanup controls pass. Both Quality jobs retain the new controls.

Evidence: `.tmp/goal-20260928-nested-fatal-closing-{v2,py312-v2}-{inputs,readback}.json`,
XML/logs and `.tmp/goal-20260928-nested-fatal-parity.json`. Both runs import current
source. The second uses the existing 3.12 interpreter with bytecode writes disabled;
all 4,956 historical package/harness/report bindings remain unchanged. This is
source proof, not fresh installed-wheel, Linux, eager/custom-factory or provider
acceptance. Those wider obligations remain separate.
