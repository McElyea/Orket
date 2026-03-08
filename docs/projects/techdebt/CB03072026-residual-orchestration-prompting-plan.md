# CB03072026 Residual Orchestration And Prompting Plan

Last updated: 2026-03-07  
Status: Active  
Owner: Orket Core

## Purpose

Cover the orchestration and prompt/contract findings from `docs/projects/techdebt/ClaudeBehavior.md` that were not explicitly enumerated in `docs/projects/techdebt/CB03072026-claude-behavior-remediation-plan.md`.

## Relationship To Primary Plan

1. This is a supplemental plan to `CB03072026-claude-behavior-remediation-plan.md`.
2. It covers the residual orchestration/workflow findings omitted from the primary plan's explicit finding inventory.
3. Domain/state-machine findings remain fully covered by the primary plan and are not repeated here.

## Contract Extraction Decision

1. No new `docs/specs/` file is extracted before this plan.
2. The source document is still a source-review artifact, not a durable contract.
3. If the strict-envelope empty-content requirement remains authoritative after revalidation, update the existing authority in `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md` in the same slice instead of leaving the rule implicit in parser code.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ARCHITECTURE.md`
5. `docs/projects/techdebt/ClaudeBehavior.md`
6. `docs/projects/techdebt/CB03072026-claude-behavior-remediation-plan.md`

## Residual Coverage

This plan covers these omitted orchestration/workflow findings:
1. finding 4
2. finding 9
3. finding 13
4. finding 14
5. finding 17
6. finding 19
7. finding 20
8. finding 21
9. finding 23

## Validated Scope

In scope:
1. Placeholder or misleading orchestration stages that appear to do real work but do not.
2. Prompt-structure, tool-result, and residue-handling semantics that currently hide degradation or rely on surprising behavior.
3. Contract-alignment work where parser/runtime behavior is stricter than the documented surface.
4. Low-to-medium severity orchestration items that are worth fixing because they reduce self-deception or make later higher-risk changes safer.

Out of scope:
1. Security-boundary and FSM items already covered by the primary plan.
2. Broad executor refactors beyond the touched residual seams.
3. New prompting features or new architecture modes.

## Success Criteria

1. Touched orchestration helpers no longer imply work that is actually a no-op or placeholder.
2. Prompt-budget, prompt-diff, and tool-result handling paths fail or degrade explicitly rather than silently.
3. The `architect_decides` path is no longer silently collapsed to `monolith` in touched orchestration code.
4. Parser and spec/documentation semantics are aligned anywhere the runtime contract is intentionally strict.

## Execution Order

1. `CB-ROP-0` revalidate the residual findings against current HEAD
2. `CB-ROP-1` contract and prompt-semantic alignment
3. `CB-ROP-2` runtime guards and observability
4. `CB-ROP-3` placeholder-stage cleanup

## Work Items

### CB-ROP-0: Revalidate Residual Findings

Problem:
1. The source review is static.
2. These findings are mostly low or medium severity, so stale items would waste time quickly.

Implementation:
1. Recheck findings 4, 9, 13, 14, 17, 19, 20, 21, and 23 against current HEAD.
2. Mark each as confirmed, already fixed, intentionally accepted, or superseded by neighboring work.
3. Drop any item that is no longer true before code changes begin.

Acceptance:
1. Each residual finding has a current-state disposition.
2. The first code slice is bounded to one touched subsystem.

Proof target:
1. review artifact update

### CB-ROP-1: Contract And Prompt-Semantic Alignment

Problem:
1. Some runtime semantics are stricter or different from what names and comments imply.
2. Prompt budgeting and prompt-diff artifacts hide surprising behavior through off-by-one or coarse partitioning.

Implementation:
1. Resolve `architect_decides` without silently forcing `monolith`.
2. Fix or explicitly document the turn-index behavior in prompt-structure diff loading.
3. Align the strict-envelope content requirement with documentation and contract authority if that rule is intentionally preserved.
4. Split or clarify prompt-budget partitioning so system prompt and protocol-contract budget treatment are not silently conflated.

Acceptance:
1. Touched prompt-structure logic matches the intended observable behavior.
2. Any intentionally strict envelope rule is documented in the authoritative contract surface.
3. Architecture-mode resolution no longer hides a real deferred decision behind a hardcoded default.

Findings addressed:
1. finding 9
2. finding 20
3. finding 21
4. finding 23

Proof target:
1. contract test
2. integration test
3. doc update if the contract remains authoritative

### CB-ROP-2: Runtime Guards And Observability

Problem:
1. Several executor paths silently assume happy-path types or heuristics.
2. Degraded recovery paths fire without enough signal to distinguish valid recovery from contract bypass.

Implementation:
1. Guard tool-dispatch result handling against non-dict middleware replacements.
2. Add observability when truncated-payload heuristics fire.
3. Decide whether `prepare_messages` should be sync or intentionally async and make the implementation truthful either way.
4. Clarify or harden the parallel-dispatch closure behavior if the surrounding inputs can mutate during concurrent execution.

Acceptance:
1. Touched degraded paths are auditable.
2. Type assumptions in touched dispatcher paths no longer explode as misleading attribute errors.
3. Async signatures in touched prompting code match actual behavior or are explicitly justified.

Findings addressed:
1. finding 13
2. finding 14
3. finding 17
4. finding 19

Proof target:
1. unit test
2. contract test

### CB-ROP-3: Placeholder-Stage Cleanup

Problem:
1. At least one named orchestration stage appears to evaluate a contract but is only an identity pass-through.

Implementation:
1. Either remove the no-op stage or mark it explicitly as a placeholder with truthful naming and comments.
2. Ensure the surrounding call path does not imply a two-stage evaluation pipeline when only one real stage exists.

Acceptance:
1. Touched guard-evaluation code no longer claims a distinct evaluation stage unless it exists.

Findings addressed:
1. finding 4

Proof target:
1. unit test
2. contract test if behavior changes

## Verification Plan

1. Prefer targeted contract and integration tests for prompt/executor behavior.
2. Use unit tests for narrow helper logic and observability branches.
3. If contract documentation is updated, verify the code path still matches the documented requirement.
4. Run `python scripts/governance/check_docs_project_hygiene.py` before handoff if docs change.

## Stop Conditions

1. Stop if a slice begins to overlap the primary plan's higher-risk executor work enough that the plans should be merged.
2. Stop and update contract authority first if parser behavior changes a stable protocol rule.
3. Do not turn these residual fixes into a broad prompt-system refactor.

## Working Status

1. `CB-ROP-0` complete
2. `CB-ROP-1` pending
3. `CB-ROP-2` in progress (`CB-ROP-2A` complete)
4. `CB-ROP-3` pending

## Progress Update

1. `CB-ROP-0` completed on 2026-03-07.
2. Revalidated the residual seams described in this plan against current HEAD instead of relying on the stale numbered finding mapping alone.
3. Confirmed still open: `orket/application/workflows/orchestrator_ops.py` still collapses non-forced architecture resolution to `monolith`; `orket/application/services/tool_parser.py` still hid unsupported truncated tool calls behind silent skips; `orket/application/workflows/turn_tool_dispatcher.py` still assumes dict-shaped post-middleware tool results.
4. Already aligned or no longer reproducing on the authoritative path: the strict-envelope `content == ""` rule already matches `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`; prompt-budget partitioning already separates protocol, tool-schema, and task buckets; the earlier prompt-diff turn-index concern no longer reproduces on the live orchestrator path because `_build_turn_context` emits 1-based turn indices; `MessageBuilder.prepare_messages` remains intentionally async to match the `TurnExecutor` contract; the semaphore wrapper binds each candidate explicitly, so the earlier closure-mutation concern does not reproduce in current `orchestrator_ops`.
5. `CB-ROP-2A` completed on 2026-03-07.
6. Added parser diagnostics for truncated-recovery paths that skip unsupported or malformed tool payloads so degraded recovery is auditable instead of silently dropping tool intents.
7. Verified with `python -m pytest tests/application/test_tool_parser.py -q`.

## Closeout Note

1. Archive this supplemental plan with the rest of the `CB03072026` cycle materials once its scoped items are completed and verified.
