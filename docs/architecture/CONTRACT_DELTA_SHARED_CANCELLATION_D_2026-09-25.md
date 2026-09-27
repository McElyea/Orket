# Shared I/O cancellation identity correction

Status: Active scoped D implementation; source/installed acceptance remains open.
Owner: Orket Core
Date: 2026-09-25
Contract: `docs/specs/SHARED_IO_CANCELLATION.md`

## Delta

The shared I/O owner previously surfaced gather's synthesized cancellation and
constructed a fresh empty cancellation after caller interruption. Real approval
transaction and Kernel paths therefore lost named operation cancellation, and
repeated external interruption lost the first caller's cancellation message.

The existing owner now retrieves the original cancellation from a settled,
cancelled operation task once and retains the first caller cancellation. Exact
`create_task(operation())` admission and gather settlement remain. Factory
evaluation timing, coroutine-only admission, one optional child cancellation,
failure precedence and upper application/Kernel lifetime policies do not change.
The earlier observer-coroutine proposal was rejected before production
integration because it changed factory timing and awaitable admission.

## Migration and validation

There is no signature, persistent-state or schema migration and no compatibility
window. Callers retain the existing operation factory and policy arguments.
Consumers observe the original named cancellation rather than an empty
replacement. Tests must retain the unchanged approval rollback/reentry
assertions and the existing prompt-counter, sandbox and governed-agent interrupt
consumers alongside the new Kernel identity/graph and first-caller controls.

The matched five-case source opening reached three named-cancellation failures;
native failure precedence and factory/admission controls passed. Opening,
closing and broader acceptance records belong to the canonical architectural-
truth plan. Supported installed CPython 3.11/3.12 execution remains required:
gather and the task's one-time retained-exception behavior cannot be accepted
from a projected patch, imports or AST checks.

## Rollback and retained effects

Changed factory timing, broadened admission, lost identity, repeated child
cancellation, abandoned cleanup or changed failure precedence blocks publication.
Repair forward through the same owner; do not replace failed proof, weaken
assertions, add another supervisor or declare an admitted effect rolled back
because its waiter was cancelled. Preserve failed/passing observations and
existing durable recovery records.

## Versioning and limits

This is a patch correction planned for 0.6.106; 0.6.105 remains the published
baseline until the candidate passes required acceptance and is committed/tagged.
No deadline, native bound, coverage target, provider selection, process cleanup
authority or broader D/E/CAP requirement changes. Source controls are not Linux,
installed-package, actual provider or whole-lane acceptance.
