# CB03072026 Claude Behavior Remediation Plan

Last updated: 2026-03-07  
Status: Active  
Owner: Orket Core

## Purpose

Convert the validated findings in `docs/projects/techdebt/ClaudeBehavior.md` into a phased remediation lane that improves truthful behavior, truthful verification, and future shippability without turning a 99-finding review into one unsafe change set.

## Contract Extraction Decision

1. No new `docs/specs/` document is being extracted before this plan.
2. `docs/projects/techdebt/ClaudeBehavior.md` is a source-review artifact, not an accepted runtime contract or requirement document.
3. The durable rules this lane depends on already exist in:
   - `AGENTS.md`
   - `CURRENT_AUTHORITY.md`
   - `docs/CONTRIBUTOR.md`
   - `docs/ARCHITECTURE.md`
   - `docs/specs/RUNTIME_INVARIANTS.md`
   - `docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`
4. If any implementation slice changes or introduces a stable cross-cutting contract that is not already covered by the authorities above, extract that contract into `docs/specs/` in the same slice before expanding implementation.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. `docs/projects/techdebt/ClaudeBehavior.md`
7. `docs/projects/techdebt/orket_behavioral_truth_review_current_state.md`
8. Current live repository state on 2026-03-07

## Planning Assumption

1. `ClaudeBehavior.md` is treated as the active finding inventory for this lane.
2. Each implementation slice must begin with quick revalidation against current HEAD because the source review is static and may overlap with already-remediated work in the repo or in neighboring techdebt documents.
3. Critical and high findings take priority; medium and low findings are only pulled in when they are in the same touched files or materially improve proof truth.

## Severity Snapshot

1. Total reviewed findings: 99
2. Critical: 5
3. High: 22
4. Medium: 41
5. Low: 31

## Validated Scope

In scope:
1. Security boundary violations and false-success surfaces identified by the audit.
2. Governance, FSM, and role-scoping truth in touched runtime paths.
3. Async-reachable service, storage, and transport boundary repairs in touched paths.
4. Orchestration, turn execution, and tool-dispatch truth where behavior is hidden behind fallback, delegation, or broad exception handling.
5. Driver, utility, and operator-facing truthfulness issues that materially affect real behavior or proof quality.
6. Verification updates needed to prove changed behavior at the right layer.
7. Techdebt lane documentation updates required to keep this cycle truthful.

Out of scope:
1. Fixing all 99 findings in one pass.
2. Broad repo-wide refactors that are not required for correctness in the touched slice.
3. New feature work unrelated to the review findings.
4. Unbounded external infrastructure setup beyond the local repo and already-configured services.
5. Archiving historical cycles that are unrelated to this active lane.

## Success Criteria

1. No touched user-facing or operator-facing success path reports success when the underlying action failed, was skipped, or was never attempted.
2. Security-sensitive touched paths enforce path containment and fail-closed subprocess behavior.
3. Touched governance and state-transition paths use the authoritative transition rules instead of bypasses or wrong entity assumptions.
4. Async-reachable touched paths stop relying on sync locks, blocking I/O, or transport-layer exceptions hidden inside service code unless the limitation is made explicit and verified.
5. New or changed tests prove observable behavior at the highest practical layer and do not over-claim runtime truth.
6. Any changed integration path is live-verified where infrastructure is available; otherwise the blocker is recorded explicitly.
7. The cycle remains archivable as a finite techdebt lane after closeout.

## Execution Order

1. `CB-0` revalidate and normalize the audit backlog
2. `CB-1` security boundaries and fail-closed external actions
3. `CB-2` governance and state-machine truth
4. `CB-3` async, service, and resource boundary repair
5. `CB-4` orchestration and executor behavioral truth
6. `CB-5` driver, utility, and operator-truth cleanup
7. `CB-6` verification, evidence, and closeout

## Work Items

### CB-0: Revalidate and Normalize the Audit Backlog

Problem:
1. `ClaudeBehavior.md` is a static source review and may contain stale, duplicate, or already-fixed findings.
2. A 99-item backlog is too large to execute safely without confirming current truth first.

Implementation:
1. Recheck every critical and high finding against current HEAD before starting code changes.
2. Collapse duplicate findings and note overlaps with `orket_behavioral_truth_review_current_state.md`.
3. Record each reviewed item as one of: confirmed, already fixed, superseded, or blocked by missing infrastructure.
4. Use that normalized set to choose the next smallest coherent slice.

Acceptance:
1. Every critical and high finding has a current-state disposition.
2. Duplicate or stale items are called out explicitly instead of silently carried forward.
3. The first implementation slice is bounded to a coherent subsystem with clear proof targets.

Proof target:
1. review artifact update
2. targeted regression-selection note

### CB-1: Security Boundaries and Fail-Closed External Actions

Problem:
1. Security-sensitive paths still permit shell execution, path traversal, weak path containment checks, or unsanitized workspace targeting.
2. Several API and webhook flows report success even when merge, comment, deployment, or cleanup actions fail or were never confirmed.
3. Some request payload bugs can silently degrade the real outcome while the caller still sees a success shape.

Implementation:
1. Replace string-shell subprocess execution with validated argv-style execution in touched paths.
2. Enforce workspace-root containment with `Path.is_relative_to()` on all touched user-supplied filesystem paths.
3. Make API and webhook success responses conditional on actual downstream success.
4. Fix request-shape issues that currently masquerade as success, including touched label-resolution and deployment-trigger paths.

Acceptance:
1. No touched subprocess path uses `shell=True`.
2. Out-of-bound filesystem inputs are rejected deterministically.
3. Touched external-action handlers do not return success before confirming the underlying action.
4. Blocked or degraded paths are surfaced explicitly to the caller or operator.

Primary findings to pull:
1. Orchestration/Workflow finding 6
2. Services/Driver/Utilities finding 17
3. API/Adapters/Webhooks findings 1, 3, 4, 8, 9, 10, 21, and 22

Proof target:
1. contract test
2. integration test
3. live verification for changed API/webhook flows where infrastructure is available

### CB-2: Governance and State-Machine Truth

Problem:
1. Touched state changes can bypass the FSM entirely or validate against the wrong entity type.
2. Governance can be weakened by missing organization context or by role construction that grants every tool to every agent.
3. Some user-visible structural or governance actions are narration-only while being surfaced as if they performed real mutations.

Implementation:
1. Route touched status mutations through the authoritative transition path.
2. Validate transitions against the real card type and available organization context.
3. Restore role-scoped tool assignment in touched team-agent construction paths.
4. Remove, downgrade, or correctly implement narration-only actions before they are presented as real operations.

Acceptance:
1. No touched mutation path silently bypasses FSM rules.
2. Tool-gate decisions are based on the real entity type and governance context.
3. Agents only receive the tools allowed by their role contracts in touched paths.
4. User-visible action surfaces match real persisted behavior.

Primary findings to pull:
1. Services/Driver/Utilities findings 3 and 5
2. Domain/State-Machine findings 1, 2, 3, 17, and 18
3. API/Adapters/Webhooks findings 13 and 14

Proof target:
1. contract test
2. integration test

### CB-3: Async, Service, and Resource Boundary Repair

Problem:
1. Async-reachable code still uses sync locks, blocking file I/O, transport-layer exceptions in service code, or one-loop-per-call execution patterns.
2. Some client and store abstractions do not match the lifecycle behavior their names imply.
3. Platform/resource constraints are claimed in code but not actually enforced in at least one important verification path.

Implementation:
1. Replace touched sync locks and blocking I/O with async-safe equivalents or explicit thread offload.
2. Keep HTTP transport exceptions at the interface layer; use domain or service exceptions below it.
3. Reuse shared async clients or connections where the abstraction claims to be a reusable client or store.
4. Make platform-specific degradation explicit when it cannot be fixed in-scope.

Acceptance:
1. Touched async paths no longer block the event loop with hidden sync primitives or file reads.
2. Service-layer code stops raising HTTP transport exceptions directly in touched paths.
3. Shared client/store abstractions match their actual lifecycle behavior.
4. Any unavoidable degraded platform behavior is explicit and test-covered.

Primary findings to pull:
1. Orchestration/Workflow findings 7, 22, and 25
2. Domain/State-Machine finding 15
3. API/Adapters/Webhooks findings 11, 17, 23, 26, 27, and 28

Proof target:
1. unit test
2. contract test
3. integration test
4. live verification for changed cross-process paths where infrastructure is available

### CB-4: Orchestration and Executor Behavioral Truth

Problem:
1. Orchestrator and turn-execution code still relies on hidden delegation, silent fallbacks, broad exception swallowing, and misleading no-op command planning.
2. Some tool-call synthesis or residue-handling paths mutate or discard data without making the degradation explicit.
3. Preflight and execution validation paths can drift because they duplicate logic.

Implementation:
1. Normalize boolean/config precedence and runtime command-plan semantics in touched orchestration paths.
2. Narrow exception handling to operational failures and let programming errors surface clearly.
3. Remove or make explicit hidden mutations, delegation shims, and duplicated validation paths in touched modules.
4. Add observability when heuristics or degraded recovery paths fire.

Acceptance:
1. Explicit-false settings are honored consistently in touched config resolution paths.
2. Programming bugs are not reported as ordinary runtime failures.
3. Tool synthesis, fallback, and truncation recovery behavior is auditable.
4. Touched orchestration paths have one authoritative validation path per concern.

Primary findings to pull:
1. Orchestration/Workflow findings 1, 2, 3, 5, 8, 10, 11, 12, 15, 16, 18, and 24

Proof target:
1. contract test
2. integration test

### CB-5: Driver, Utility, and Operator-Truth Cleanup

Problem:
1. Driver/support code and utilities still contain misleading defaults, hidden no-ops, CWD-relative paths, weak determinism helpers, and observability gaps.
2. Several of these items are self-deception debt: names, comments, or telemetry suggest a stronger runtime guarantee than the code actually provides.

Implementation:
1. Fix touched driver and utility paths that rely on CWD drift, unsorted canonicalization, fake autodetection, or hidden normalization shortcuts.
2. Replace misleading placeholders and no-ops with explicit degraded behavior where a real implementation is out of scope.
3. Take low-severity cleanup only when it is in files already touched by higher-priority work or when a standalone fix materially improves proof truth.

Acceptance:
1. Touched helper and driver code no longer depends on CWD-relative behavior or misleading silent normalization.
2. Operator-visible text matches actual runtime behavior in touched areas.
3. Touched determinism and reproducibility helpers are deterministic on repeated runs.

Primary findings to pull:
1. Services/Driver/Utilities findings 1, 2, 7, 8, 10 through 12, 15, 16, 19, 20, 21, 22, and 23
2. Domain/State-Machine findings 4 through 14, 16, 19, 20, and 21
3. API/Adapters/Webhooks findings 5, 6, 7, 12, 15, 16, 19, 20, 24, 25, 29, and 30

Proof target:
1. unit test
2. contract test
3. integration test where touched behavior crosses a process boundary

### CB-6: Verification, Evidence, and Closeout

Problem:
1. This lane only helps if the proof is truthful and the active techdebt folder stays bounded.
2. Integration-path changes require real end-to-end verification before we can declare them complete.

Implementation:
1. For each completed slice, add or update tests at the highest practical layer and label new or modified tests by layer.
2. Run targeted pytest modules for the slice before broadening to the canonical repo test command.
3. Run real API, webhook, provider, or cross-process flows for any changed integration path and record the observed path and result.
4. Run `python scripts/governance/check_docs_project_hygiene.py` before handoff or archive.
5. When this cycle is complete and superseded, move the cycle docs to `docs/projects/archive/techdebt/CB03072026/`.

Acceptance:
1. Every completed slice states what was verified, at what layer, and what remains blocked.
2. Integration-path changes are either live-verified or explicitly marked environment-blocked.
3. The active `docs/projects/techdebt/` folder keeps only maintenance docs and current cycle docs.

Proof target:
1. targeted pytest runs
2. `python -m pytest -q`
3. live verification evidence for changed integrations
4. `python scripts/governance/check_docs_project_hygiene.py`

## Suggested First Collaboration Slices

1. `CB-3A` `coordinator_store` async/service-boundary repair

## Progress Update

1. `CB-1A` completed on 2026-03-07.
2. Revalidated API findings 8, 9, and 10 against current HEAD and confirmed they were still open before the code change.
3. Hardened `runs_root`, `sqlite_db_path`, and `req.workspace` in `orket/interfaces/routers/sessions.py` so caller-supplied paths are resolved relative to the authoritative workspace root and rejected when they escape it.
4. Verified with `python -m pytest tests/interfaces/test_sessions_router_protocol_replay.py -q` and `python -m pytest tests/interfaces/test_api_interactions.py -q`.
5. `CB-2A` completed on 2026-03-07.
6. Revalidated domain/state-machine findings 1, 2, and 3 against current HEAD and confirmed `system_set_status` still bypassed transition enforcement while `ToolGate` still skipped FSM validation without an org and validated all transitions as `CardType.ISSUE`.
7. Routed `system_set_status` through the normal workflow/gate/dependency path with required override metadata, made `ToolGate` enforce transitions regardless of org presence, and propagated stored `card_type` through the card tools and gate context.
8. Verified with `python -m pytest tests/core/test_workitem_transition_contract.py tests/core/test_card_management_state_machine.py tests/core/test_tool_gate_state_change_contract.py -q` and `python -m pytest tests/integration/test_tool_gating.py -q`.
9. `CB-1B` completed on 2026-03-07.
10. Revalidated API/webhook findings 3, 4, and 22 against current HEAD and confirmed merge, escalation/rejection comment, requirements-issue, and sandbox deployment paths could still report success after downstream failure.
11. Made webhook merge/reject/deployment handlers return real downstream outcomes, fail closed on HTTP failures, and surface degraded sandbox deployment results instead of unconditional success messages.
12. Verified with `python -m pytest tests/adapters/test_gitea_webhook.py -q`.
13. Live verification rerun on 2026-03-07 against local Gitea and the primary signed `/webhook/gitea` path succeeded for merge, escalation, and auto-reject after fixing requirements-issue label ID resolution; the merged deployment path truthfully reported a degraded sandbox deployment caused by missing generated backend/frontend paths.
14. `CB-4A` completed on 2026-03-07.
15. Revalidated orchestration findings 3 and 5 against current HEAD and confirmed explicit-false env values still fell through to org/default config while the runtime verifier still claimed profile defaults that did not exist and accepted shell-string commands.
16. Fixed `_resolve_bool_flag` precedence so explicit false env values win over org config, gave Python/polyglot runtime verification one real builtin command, and made shell-string verifier commands fail explicitly instead of executing with `shell=True`.
17. Verified with `python -m pytest tests/application/test_runtime_verifier_service.py tests/application/test_orchestrator_bool_flag_resolution.py -q`.

## Verification Plan

Per-slice verification:
1. Prefer contract or integration proof for user-visible behavior changes.
2. Add targeted unit coverage only for edge cases that are hard to reach from higher-layer tests.
3. For changed integration paths, run the real flow end-to-end and record whether the observed path was primary, fallback, degraded, or blocked.
4. If live verification is impossible because credentials, services, or infrastructure are unavailable, record the exact blocker instead of over-claiming completion.

Lane-close verification:
1. Run slice-targeted `pytest` modules first.
2. Run `python -m pytest -q` before declaring the cycle complete.
3. Run `python scripts/governance/check_docs_project_hygiene.py`.

## Stop Conditions

1. Stop a slice if it grows beyond the smallest coherent subsystem needed for correctness.
2. Stop and extract a spec first if a slice changes a stable cross-cutting contract not already covered by current authority.
3. Stop and record an environment blocker if required live verification depends on unavailable credentials, services, or infrastructure.
4. Do not close the lane on static review alone for API, webhook, provider, or other integration-path changes.

## Working Status

1. `CB-0` pending
2. `CB-1` complete (`CB-1A` complete; `CB-1B` complete; live verification complete`)
3. `CB-2` in progress (`CB-2A` complete)
4. `CB-3` pending
5. `CB-4` in progress (`CB-4A` complete)
6. `CB-5` pending
7. `CB-6` pending

## Closeout Note

1. This plan remains in the active `docs/projects/techdebt/` folder because it is the current cycle plan for an active maintenance lane.
