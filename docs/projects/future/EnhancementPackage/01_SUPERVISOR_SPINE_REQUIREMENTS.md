# Supervisor Spine Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Runtime supervision

## Purpose

Define one bounded next-step supervision delta beyond the already-shipped Packet 1 approval family.

This lane exists to harden the supervisor spine without pretending to solve:
1. universal safe-tooling coverage,
2. full workflow composition,
3. full memory architecture,
4. broad product UX,
5. broad approval architecture redesign.

## Current shipped baseline

Current authority already ships a bounded approval-checkpoint family.
That baseline includes admitted Packet 1 approval slices, bounded decision vocabulary, and same-governed-run continuation on the shipped paths.
This doc does not claim that approval semantics are absent today.

## Future delta proposed by this doc

This doc proposes one explicit next-step delta beyond the shipped approval family.
Any adoption of this doc must name that delta precisely.
Acceptable examples include:
1. same-attempt versus new-attempt truth hardening for an already-shipped approval slice,
2. richer operator-visible checkpoint and continuation lineage for an already-shipped approval slice,
3. one newly admitted approval-required capability family added under an explicit contract.

The key rule is that adoption must name one exact delta slice rather than speaking generically about approval-required capabilities.

## What this doc does not reopen

This doc does not reopen:
1. universal safe-tooling convergence,
2. broad ControlPlane convergence,
3. a repo-wide approval redesign,
4. unrestricted approval-gated execution for all mutation paths.

## Usage boundary

This doc should be read as a bounded requirements candidate for explicit future adoption.

It should not be read as:
1. a claim that all governed mutation paths are already approval-checkpoint capable,
2. a claim that resume is globally available,
3. a reason to reopen broad ControlPlane convergence by implication,
4. a claim that current Packet 1 approval semantics are unshipped.

## In scope

1. one named delta slice beyond the already-shipped Packet 1 approval family,
2. interrupt, approve, deny, and resume truth for that named slice,
3. one stable checkpoint-backed continuation path for that named slice,
4. operator-visible approval lineage,
5. operator-visible continuation lineage,
6. same-attempt versus new-attempt semantics where the named slice requires that distinction,
7. one bounded live event vocabulary for the admitted delta slice.

## Out of scope

1. universal safe-tooling coverage,
2. full workflow DSL work,
3. full memory or retrieval architecture,
4. broad client UX work,
5. broad multi-capability approval orchestration,
6. marketplace or extension-distribution concerns.

## Core requirements

### SS-01. Adoption must name one exact delta slice
Any adoption of this doc must name one exact supervision delta beyond current shipped Packet 1 approval authority.
Generic approval expansion language is insufficient.

### SS-02. Shipped Packet 1 semantics remain the baseline
The lane must preserve and accurately describe the already-shipped approval family rather than redefining it informally.

### SS-03. Interrupt before protected effect
The named delta slice must interrupt before the protected effect boundary and must not rely on post-hoc correction as the primary control.

### SS-04. Explicit durable approval state
Approval state for the named slice must be durable and attributable to the governing run, attempt, and step.

### SS-05. Bounded decision vocabulary
The admitted approval surface must expose a bounded decision vocabulary.
At minimum:
1. approve,
2. deny.

Optional operator metadata may be admitted, but it must not silently create a second continuation path.

### SS-06. Checkpoint-backed continuation only
Continuation must require:
1. an admitted checkpoint where the slice depends on checkpoint semantics,
2. a durable approval decision where required,
3. a supervisor-owned continuation decision.

Continuation must not occur merely because runtime state happened to be saved.

### SS-07. Same-attempt versus new-attempt truth
Where the named slice can continue existing work or create a retry path, the runtime must make same-attempt continuation and new-attempt retry visibly distinct.
The lane must not allow continuation semantics to erase attempt history.

### SS-08. Approval and continuation lineage
The runtime must publish operator-visible lineage showing:
1. why approval was requested,
2. what object requested it,
3. what decision was made,
4. when continuation occurred,
5. whether continuation stayed in the same attempt or created a new attempt.

### SS-09. Fail closed without required approval
The named slice must fail closed when approval is required but missing, unreadable, stale, or structurally invalid.

### SS-10. One bounded event vocabulary
The lane must define one bounded event family for the named slice.
At minimum it must distinguish:
1. approval requested,
2. approval resolved,
3. continuation started,
4. continuation completed or terminally failed.

### SS-11. No hidden alternate continuation paths
Endpoint behavior, logs, cached state, or operator notes must not act as alternate continuation authority.

## Acceptance boundary

This lane is acceptable only when:
1. one exact supervision delta beyond current shipped Packet 1 authority is named,
2. one stable checkpoint-backed continuation path exists where the named slice requires it,
3. the named slice fails closed without required approval,
4. approval and continuation lineage are operator-visible,
5. same-attempt versus new-attempt truth is explicit where relevant,
6. no hidden alternate continuation path remains authoritative for the admitted slice.

## Proof requirements

Structural proof:
1. no continuation-by-snapshot-existence path,
2. no approval-required effect path without durable approval state,
3. no hidden operator metadata field creates alternate continuation authority,
4. no attempt-history collapse between continuation and retry,
5. no adoption text leaves the named delta slice ambiguous.

Integration proof:
1. the named slice interrupts before effect,
2. an approval decision unblocks only the admitted continuation path,
3. deny terminally blocks the admitted effect path,
4. stale or missing approval fails closed,
5. emitted lineage distinguishes request, decision, and continuation.

Live proof where real surfaces are involved:
1. an approval-required run pauses visibly,
2. approve resumes the admitted path,
3. deny prevents the protected effect,
4. the resulting artifacts show truthful approval and continuation lineage.

## Ordering note

This doc is first in the packet because a truthful next-step supervision delta is the strongest bounded runtime move available.
