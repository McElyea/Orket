# Brutal Code Review: Behavioral Lies and Architectural Issues

Last updated: 2026-03-23
Status: Active review memo with remediation status updates
Owner: Codex review pass

Scope: targeted deep review of runtime-truth, replay/audit, sandbox lifecycle, review-run, and API boundary code. This is not a claim that every file in the repository was read. It is a claim that every issue found in this pass is listed below.

## Resolution update

Resolved in the 2026-03-23 remediation pass:

1. Ship-risk item 1: cleanup verification now distinguishes incomplete observation from verified absence, and the sandbox lifecycle fails closed when Docker resource observation is unavailable.
2. Ship-risk item 2: compose cleanup no longer bypasses positive authority when unlabeled or blocked resources are present.
3. Ship-risk item 3: kernel commit/replay/audit no longer treat a caller-supplied execution-result digest as proof that execution occurred; digest-only state is surfaced as `claimed_only`.
4. Ship-risk item 4: `review pr` now binds `--remote` to a configured git remote for the requested repo and rejects unbound or non-HTTP(S) remotes before sending authenticated requests.
5. Ship-risk item 5: `review files` now fails closed when any requested path cannot be loaded from the requested ref.
6. Exploration-safe item 6: [orket/interfaces/routers/sessions.py](orket/interfaces/routers/sessions.py) now depends on [orket/application/services/protocol_replay_service.py](orket/application/services/protocol_replay_service.py) for replay, compare, and parity behavior instead of constructing storage/runtime comparison authority inline.
7. Exploration-safe item 8: [orket/interfaces/api.py](orket/interfaces/api.py) no longer hides runtime authority behind `_ApiRuntimeNodeProxy` / `_EngineProxy` `__getattr__` delegation. The API now uses explicit runtime objects.
8. Self-deception item 9: cleanup verification no longer treats empty observation as verified absence.
9. Self-deception item 10: kernel commit/replay/audit no longer narrate execution from digest-shaped strings alone.
10. Self-deception item 11: companion model catalog failure now returns a truthful degraded error response (`ok=false`, `degraded=true`, HTTP 503) instead of a fabricated success payload.

Still open after this pass:

1. Exploration-safe item 7 remains active. Decision nodes still own runtime construction, environment reads, and invocation selection on live authority paths. This pass reduced adjacent drift but did not retire that architectural exception.

Live verification completed later on 2026-03-23 once Docker became available:

1. Ship-risk items 1 and 2 now have live Docker acceptance proof in addition to targeted contract/integration coverage.
2. Ship-risk items 3, 4, and 5 have live localhost/subprocess proof in this session.

## Ship-risk debt

1. Sandbox cleanup can be marked "verified complete" when Docker inspection failed, not when cleanup was actually observed.
   - Code: [orket/application/services/sandbox_runtime_lifecycle_service.py](orket/application/services/sandbox_runtime_lifecycle_service.py) lines 108-123 and 354-370; [orket/application/services/sandbox_runtime_cleanup_service.py](orket/application/services/sandbox_runtime_cleanup_service.py) lines 99-143; [orket/application/services/sandbox_cleanup_verification_service.py](orket/application/services/sandbox_cleanup_verification_service.py) lines 47-57.
   - Why this is bad: `_list_resources()` turns any Docker CLI failure into `[]`. That empty observation is then treated as "nothing remains", and the cleanup path can transition to `CLEANUP_VERIFIED_COMPLETE`. The same observation path is used to seed `managed_resource_inventory` during deployment verification, so a failed observation can poison the lifecycle record early and make later cleanup "truth" impossible to trust.
   - Status: fixed in code on 2026-03-23. Verification now fails closed on incomplete observation.
   - Verification: live Docker acceptance passed on 2026-03-23 via [tests/acceptance/test_sandbox_orchestrator_live_docker.py](tests/acceptance/test_sandbox_orchestrator_live_docker.py), [tests/acceptance/test_sandbox_runtime_recovery_live_docker.py](tests/acceptance/test_sandbox_runtime_recovery_live_docker.py), [tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py](tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py), and [tests/acceptance/test_sandbox_cleanup_leak_gate.py](tests/acceptance/test_sandbox_cleanup_leak_gate.py). These routes prove cleanup completion only when labeled Docker resources are actually gone.

2. The sandbox cleanup authority check effectively bypasses its own positive-authority safeguard for compose cleanup.
   - Code: [orket/application/services/sandbox_cleanup_authority_service.py](orket/application/services/sandbox_cleanup_authority_service.py) lines 60-65.
   - Why this is bad: `compose_cleanup_allowed` is gated by `(positive_authority_present or bool(record.compose_project))`. `record.compose_project` is truthy for every real record, so the positive-label check is functionally dead for compose cleanup. If the compose file exists and the project name has the expected prefix, cleanup is authorized even when the observed resources are unlabeled and already classified as blocked.
   - Status: fixed in code on 2026-03-23. Compose cleanup no longer overrides blocked-resource truth.
   - Verification: live Docker acceptance passed on 2026-03-23 via [tests/acceptance/test_sandbox_orchestrator_live_docker.py](tests/acceptance/test_sandbox_orchestrator_live_docker.py) and [tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py](tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py). These routes prove cleanup is blocked when ownership is not trusted and that unlabeled/unverified compose projects are classified as unverified rather than auto-cleaned.

3. Kernel action lifecycle can claim that an action executed even when the caller only supplied an arbitrary digest.
   - Code: [orket/kernel/v1/nervous_system_runtime.py](orket/kernel/v1/nervous_system_runtime.py) lines 286-287 and 361-405; [orket/kernel/v1/nervous_system_runtime_extensions.py](orket/kernel/v1/nervous_system_runtime_extensions.py) lines 112-150 and 323-327.
   - Why this is bad: `commit_proposal_v1()` emits `action.executed` and `action.result_validated` whenever `status == "COMMITTED"` and `execution_result_digest` is non-empty. There is no verification that the digest corresponds to a real execution artifact or even to an execution payload. Replay and audit then treat the presence of those events as proof that execution happened.
   - Status: fixed in code on 2026-03-23. Replay/audit now surface digest-only state as `claimed_only` and no longer emit execution-validation events from digest presence alone.
   - Verification: live evidence passed via `tests/scripts/test_nervous_system_live_evidence.py`, which runs the real subprocess-backed proof script and verifies the resulting artifact.

4. Review PR mode can exfiltrate a Gitea token to an arbitrary host.
   - Code: [orket/interfaces/orket_bundle_cli.py](orket/interfaces/orket_bundle_cli.py) lines 699-702 and 984-993; [orket/application/review/run_service.py](orket/application/review/run_service.py) lines 81-93 and 122-129; [orket/application/review/snapshot_loader.py](orket/application/review/snapshot_loader.py) lines 289-305.
   - Why this is bad: the CLI accepts arbitrary `--remote` and `--token` input, `_resolve_token()` will also pull a token from `ORKET_GITEA_TOKEN` / `GITEA_TOKEN`, and `load_from_pr()` unconditionally attaches `Authorization: token ...` to whatever base URL was supplied. There is no host validation, no scheme restriction, and no binding to the local repo's configured remote.
   - Status: fixed in code on 2026-03-23. `review pr` now requires the requested base URL to match a configured git remote for the requested repo before any authenticated request is made.
   - Verification: live end-to-end tests passed against a localhost stub server. The bound-remote path proves token attachment only on the accepted remote, and the unbound-remote path proves rejection before any HTTP request is sent.

5. Review files mode silently converts "file missing at ref" into "reviewed empty file" and still returns a successful review run.
   - Code: [orket/application/review/snapshot_loader.py](orket/application/review/snapshot_loader.py) lines 244-254; [orket/application/review/run_service.py](orket/application/review/run_service.py) lines 204-217 and 272-303.
   - Why this is bad: `load_from_files()` appends the requested path to `changed_files`, swallows `git show` failure, and records an empty blob/diff block. The caller receives a structurally valid snapshot and `_execute()` still returns `ok=True`. That means the system can claim a file was reviewed when its content was never loaded.
   - Status: fixed in code on 2026-03-23. Missing files now raise and abort the review run instead of fabricating reviewed content.
   - Verification: live end-to-end test passed against a real temporary git repo and confirmed `review files` fails closed on a missing path.

## Exploration-safe debt

6. The sessions router is directly implementing replay/parity/storage policy instead of depending on an application service boundary.
   - Code: [orket/interfaces/routers/sessions.py](orket/interfaces/routers/sessions.py) lines 11-17 and 213-323.
   - Why this is bad: the HTTP layer imports storage adapters and runtime comparison engines directly, constructs repositories itself, chooses database locations, and exposes replay/parity policy inline. That is interface-layer ownership of application and adapter concerns.
   - Architecture drift: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) lines 34-39 list only `orket/interfaces/api.py`, `orket/interfaces/coordinator_api.py`, and `orket/interfaces/orket_bundle_cli.py` as known interface-layer dependency exceptions. `sessions.py` is not listed there.

7. "Decision nodes" are still acting as runtime authorities, object factories, and environment readers rather than bounded recommendation functions.
   - Code: [orket/decision_nodes/api_runtime_strategy_node.py](orket/decision_nodes/api_runtime_strategy_node.py) lines 18-21, 45, 59, 73, 75-133, 206-265; [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py) lines 462-464, 520-526, 556-580, 603-605, and 749-751.
   - Why this is bad: these nodes read environment variables, generate timestamps and UUIDs, inspect filesystem state, choose method invocations, bootstrap environment, construct orchestrators/pipelines/providers, and wire sub-pipelines. That is execution authority and runtime construction, not advisory strategy.
   - Architecture status: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) lines 38-39 already acknowledge this as transition debt, but the active API and orchestration surface still route through it. This remains a high-leverage architectural cleanup target because it keeps volatility inside the authority path.

8. The API surface hides critical authority behind global proxy/singleton indirection.
   - Code: [orket/interfaces/api.py](orket/interfaces/api.py) lines 62-93.
   - Why this is bad: `_ApiRuntimeNodeProxy` and `_EngineProxy` use `__getattr__`-based lazy delegation over process-global singletons. That makes ownership opaque, couples request handling to hidden cached state, and makes isolation/reset behavior harder to reason about. Even when the behavior is currently correct, this is exactly the kind of indirection that causes authority drift to go unnoticed.

## Self-deception debt

9. The cleanup verification test suite currently locks in a false-green interpretation of "observed nothing."
   - Evidence: [tests/integration/test_sandbox_cleanup_verification_service.py](tests/integration/test_sandbox_cleanup_verification_service.py) lines 64-70.
   - Why this matters: the test names the behavior as success instead of requiring the caller to distinguish "verified absent" from "inspection unavailable". That makes the lie in item 1 harder to fix because the suite treats it as contract.

10. The kernel operator-path tests lock in digest-only execution claims as valid proof.
   - Evidence: [tests/kernel/v1/test_nervous_system_runtime.py](tests/kernel/v1/test_nervous_system_runtime.py) lines 167-174 and [tests/interfaces/test_api_nervous_system_operator_surfaces.py](tests/interfaces/test_api_nervous_system_operator_surfaces.py) lines 74-78 and 119-135.
   - Why this matters: the tests reward a path where the system says "executed" because a caller supplied a digest-shaped string. That is not runtime truth; it is narrated execution.

11. The companion-model fallback is intentionally standardized as a fabricated success payload.
   - Code: [orket/interfaces/routers/companion.py](orket/interfaces/routers/companion.py) lines 97-113.
   - Standardized by: [orket/runtime/degradation_first_ui_standard.py](orket/runtime/degradation_first_ui_standard.py) lines 35-38 and [tests/runtime/test_degradation_first_ui_standard.py](tests/runtime/test_degradation_first_ui_standard.py) lines 24-27.
   - Why this matters: `degraded=True` is truthful, but `ok=True` plus a guessed provider/model list is still a fabricated catalog response. It is a small lie, but it is now documented and tested as expected behavior rather than treated as a recoverable operator-visible failure.

## Assumptions

- I treated "runtime truth" defects as higher severity than ordinary style debt.
- I treated a payload as deceptive when it claims or strongly implies verified runtime state that the code did not actually verify.
- I treated already-documented architecture exceptions as still worth calling out when they continue to sit on active authority paths.

## Suggested order of attack

1. Fix the sandbox lifecycle truth path first. It is the highest-risk combination of real side effects, cleanup authority, and false-green verification.
2. Fix the kernel digest-only execution claim next. Audit and replay surfaces should never accept narrated execution as proof.
3. Lock down review-run inputs after that. Token exfiltration and silent missing-file review both poison trust in the review system itself.
4. Then collapse interface-layer and decision-node authority drift into explicit application services so future verification has a clear owner.
