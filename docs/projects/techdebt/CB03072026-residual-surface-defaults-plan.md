# CB03072026 Residual Surface And Defaults Plan

Last updated: 2026-03-07  
Status: Active  
Owner: Orket Core

## Purpose

Cover the driver, extension, policy-default, and small interface-surface findings from `docs/projects/techdebt/ClaudeBehavior.md` that were not explicitly enumerated in `docs/projects/techdebt/CB03072026-claude-behavior-remediation-plan.md`.

## Relationship To Primary Plan

1. This is a supplemental plan to `CB03072026-claude-behavior-remediation-plan.md`.
2. It covers the residual services/driver/utilities findings and the remaining API/operator-surface findings omitted from the primary plan's explicit inventory.
3. It intentionally focuses on smaller truth and default-surface seams rather than the primary plan's higher-risk governance and security slices.

## Contract Extraction Decision

1. No new `docs/specs/` file is extracted before this plan.
2. These residual items are implementation and operator-surface truth issues, not new accepted requirement documents.
3. If any slice changes a stable runtime contract instead of only fixing implementation truth, update the existing authority document in the same slice.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ARCHITECTURE.md`
5. `docs/projects/techdebt/ClaudeBehavior.md`
6. `docs/projects/techdebt/CB03072026-claude-behavior-remediation-plan.md`

## Residual Coverage

This plan covers these omitted findings:
1. Services/Driver/Utilities finding 4
2. Services/Driver/Utilities finding 6
3. Services/Driver/Utilities finding 9
4. Services/Driver/Utilities finding 13
5. Services/Driver/Utilities finding 14
6. Services/Driver/Utilities finding 18
7. Services/Driver/Utilities finding 24
8. Services/Driver/Utilities finding 25
9. API/Adapters/Webhooks finding 2
10. API/Adapters/Webhooks finding 18

## Validated Scope

In scope:
1. Template and registry defaults that currently advertise structure the runtime does not actually honor.
2. Surface-level API and operator messages that misdescribe the true behavior.
3. Small adapter and helper fixes that reduce self-deception without broad refactors.
4. Lifecycle and fallback semantics for touched extension, policy-node, and coordinator surfaces.

Out of scope:
1. The primary plan's security-boundary, webhook-success, FSM, and async service slices.
2. Large interface rewrites or dependency-injection migrations beyond the touched residual surfaces.
3. New policy-node features beyond truthful fallback or documentation.

## Success Criteria

1. Touched templates and registries do not reference undefined roles or silently seed production state with demo data.
2. Touched extension and helper APIs are explicit enough that their observable behavior matches their surface claims.
3. Touched fallback and cleanup paths are either implemented truthfully or clearly marked as degraded/limited.
4. Operator-visible logs and messages in touched surfaces describe the actual runtime result.

## Execution Order

1. `CB-RSD-0` revalidate the residual findings against current HEAD
2. `CB-RSD-1` template and default-surface truth
3. `CB-RSD-2` extension and helper API truth
4. `CB-RSD-3` fallback, cleanup, and operator-message truth

## Work Items

### CB-RSD-0: Revalidate Residual Findings

Problem:
1. These are smaller residual items and are more likely to have moved since the source review.

Implementation:
1. Recheck services findings 4, 6, 9, 13, 14, 18, 24, and 25.
2. Recheck API findings 2 and 18.
3. Mark each as confirmed, already fixed, accepted limitation, or superseded before coding.

Acceptance:
1. Each residual finding has a current-state disposition.
2. The implementation order is based on confirmed current truth, not stale review text.

Proof target:
1. review artifact update

### CB-RSD-1: Template And Default-Surface Truth

Problem:
1. Some touched surfaces advertise valid defaults while emitting inconsistent or demo-only data.

Implementation:
1. Make the team template and role definitions internally consistent.
2. Remove demo-card seeding from the coordinator API singleton path or replace it with a truthful initialization pattern.
3. Keep any touched default or template surface aligned with what production callers should actually expect.

Acceptance:
1. Touched templates no longer reference undefined roles.
2. Importing the coordinator API does not seed production-visible demo data.

Findings addressed:
1. Services finding 4
2. API finding 2

Proof target:
1. contract test
2. integration test

### CB-RSD-2: Extension And Helper API Truth

Problem:
1. Several touched helpers and managers hide their real API or imply broader capability than they actually provide.

Implementation:
1. Replace or reduce `__getattr__` delegation where it hides the real extension-manager surface.
2. Make truncated-tool recovery limitations explicit or diagnostic instead of silently generic.
3. Clarify conversation-routing semantics so "not structural" is not mislabeled as "conversation."
4. Remove low-value duplicate parsing behavior in touched helper code when the fix is truly minimal.

Acceptance:
1. Touched helper/manager surfaces are explicit enough for static discovery and clearer runtime failure modes.
2. Recovery or routing limitations are named and observable rather than implied as generic capability.

Findings addressed:
1. Services finding 9
2. Services finding 13
3. Services finding 14
4. Services finding 24

Proof target:
1. unit test
2. contract test

### CB-RSD-3: Fallback, Cleanup, And Operator-Message Truth

Problem:
1. Some touched caches, cleanup paths, and policy defaults work only partially or communicate the wrong thing to operators.

Implementation:
1. Make the VRAM cache safe for concurrent access in its actual usage model.
2. Make optional async-model cleanup behavior explicit when no cleanup hook exists.
3. Make unsupported sandbox tech-stack behavior fail truthfully or degrade through a documented default.
4. Fix misleading operator log wording where the runtime rejects requests but the message implies auth is disabled.

Acceptance:
1. Touched caches and cleanup paths no longer hide surprising lifecycle behavior.
2. Unsupported default-policy cases are explicit and test-covered.
3. Operator log text matches the actual reject-by-default behavior.

Findings addressed:
1. Services finding 6
2. Services finding 18
3. Services finding 25
4. API finding 18

Proof target:
1. unit test
2. contract test
3. integration test where touched behavior is operator-facing

## Verification Plan

1. Prefer targeted tests around the touched default surfaces rather than broad regression work.
2. Use integration tests where import-time or request-surface behavior changes.
3. If a slice changes operator-facing logs or messages, verify the exact emitted text in tests where practical.
4. Run `python scripts/governance/check_docs_project_hygiene.py` before handoff if docs change.

## Stop Conditions

1. Stop if a slice starts to depend on the larger security or async-boundary work already scoped in the primary plan.
2. Do not expand these residual fixes into a repo-wide dependency-injection or extension-framework rewrite.
3. Keep standalone cleanup truly minimal unless it directly improves truthful behavior or verification.

## Working Status

1. `CB-RSD-0` pending
2. `CB-RSD-1` pending
3. `CB-RSD-2` pending
4. `CB-RSD-3` pending

## Closeout Note

1. Archive this supplemental plan with the rest of the `CB03072026` cycle materials once its scoped items are completed and verified.
