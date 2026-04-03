# Session Continuity Requirements

Last updated: 2026-04-02
Status: Draft staged future-lane requirements
Authority status: Staging only. Not current roadmap authority. Not current execution authority until explicitly adopted.
Owner: Orket Core
Lane family: Runtime continuity

## Purpose

Define one bounded next-step continuity delta beyond the already-shipped host-owned session boundary.

This lane exists to harden continuity into a stronger runtime primitive without pretending that session identity and inspection are absent today.

## Current shipped baseline

Current authority already ships a bounded session boundary.
That baseline includes host-owned interaction sessions, session inspection surfaces, replay and snapshot inspection, and a bounded continuity input vocabulary on the admitted Packet 1 path.
This doc does not claim that canonical session identity or provider-shaped context inputs are wholly unshipped.

## Future delta proposed by this doc

This doc proposes continuity hardening beyond the shipped baseline.
Candidate deltas include:
1. stronger session versus profile versus workspace memory separation,
2. clearer provider pluggability and provider contribution lineage,
3. stronger summary and cleanup-adjacent inspection semantics,
4. stricter protection against client-owned continuity drift.

For clarity, this proposed delta does not reopen deletion authority, retention policy authority, workspace-cleanup authority, or broad memory-platform authority.

## What this doc does not reopen

This doc does not reopen:
1. broad Companion product UX,
2. voice-product behavior,
3. broad retrieval or memory-ranking research,
4. moving runtime authority into a gateway, frontend, or thin client,
5. deletion authority, retention-policy authority, workspace-cleanup authority, or broad memory-platform authority.

## Usage boundary

This doc should be read as a continuity-primitive requirements candidate.

It should not be read as:
1. a social Companion product plan,
2. a broad memory-ranking ambition,
3. permission to move runtime authority into a thin client or frontend repo,
4. a claim that the current host-owned session boundary is absent.

## In scope

1. one bounded delta over the already-shipped session boundary,
2. stronger session identity posture where needed,
3. session memory versus profile memory versus workspace memory separation,
4. a more explicit context-provider pipeline,
5. provider contribution lineage,
6. session lineage, summary, replay, and cleanup-adjacent inspection hardening,
7. host-owned continuity authority,
8. inspection-only operator session surfaces unless separately contracted.

## Out of scope

1. broad frontend product work,
2. voice UX details,
3. broad knowledge ranking or retrieval-quality research,
4. general-purpose social memory ambitions,
5. moving orchestration authority into client repos.

## Core requirements

### SC-01. Shipped session boundary remains the baseline
Any adoption of this doc must start from the existing host-owned session boundary and must not describe the lane as though it is introducing session authority from zero.

### SC-02. One continuity identity story
The runtime must retain one canonical session object distinct from individual run or turn invocation objects.
A future delta must strengthen that identity story, not fork it.

### SC-03. Session identity survives multiple turns
A session must remain the continuity identity across subordinate invocations that belong to the same operator-visible interaction.

### SC-04. Memory family separation is explicit
The runtime must distinguish at minimum:
1. session memory,
2. profile memory,
3. workspace memory.

These families must not silently collapse into one generic store on the admitted path.

### SC-05. Provider pipeline is explicit and host-owned
Context injection must occur through an explicit host-owned provider pipeline rather than hidden in-workload or client-owned glue.

### SC-06. Provider contribution lineage is inspectable
The runtime must make provider contribution lineage inspectable.
At minimum it must be possible to tell:
1. which provider contributed,
2. what class of context it contributed,
3. where in the provider order it executed.

### SC-07. Session replay stays inspection-only unless separately contracted
Session replay and session snapshots must remain inspection surfaces unless a separate authority contract explicitly grants continuation semantics.

### SC-08. Summary and cleanup-adjacent inspection semantics are explicit
The runtime must define bounded summary and cleanup-adjacent inspection semantics for:
1. session termination,
2. subordinate turn cancellation,
3. visibility into retention-sensitive session state.

This requirement does not grant deletion authority, retention-policy authority, workspace-cleanup authority, or broad memory-platform authority by implication.

### SC-09. Continuity inputs remain bounded
The lane must define the admitted continuity input vocabulary rather than letting arbitrary workload-local or client-local state become invisible continuity authority.

### SC-10. No client-owned continuity center
Thin clients, gateways, or external presentation repos must not become a second hidden session-authority center.

## Acceptance boundary

This lane is acceptable only when:
1. one bounded continuity delta over the shipped session boundary is named,
2. one canonical session model remains intact,
3. memory-family separation is explicit,
4. providers are explicit and inspectable,
5. session replay and summary surfaces are operator-visible,
6. cleanup-adjacent inspection semantics are bounded and inspectable,
7. the host remains the sole runtime authority for continuity.

## Proof requirements

Structural proof:
1. no hidden client-owned continuity store acts as runtime authority,
2. no provider injection occurs through undocumented side channels,
3. no session replay surface implies continuation by default,
4. no memory-family collapse occurs on the admitted path,
5. no adoption text understates the already-shipped baseline.

Integration proof:
1. a session spans multiple subordinate turns,
2. provider order is stable and inspectable,
3. session, profile, and workspace memory remain distinguishable,
4. session cancellation and cleanup-adjacent inspection produce bounded truthful results without claiming deletion, retention, or workspace-cleanup authority.

Live proof where real surfaces are involved:
1. operator session inspection shows stable identity across multiple turns,
2. the session snapshot surfaces provider lineage,
3. cleanup-adjacent actions do not fabricate deletion, retention, workspace-cleanup, or continuation claims.

## Ordering note

This doc is second in the packet because continuity hardening should follow a stronger interruptible supervisor spine and should precede product-specific continuity UX.
