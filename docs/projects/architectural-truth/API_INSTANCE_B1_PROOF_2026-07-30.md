# Architectural Truth API Instance B1 Proof

Date: 2026-07-30
Status: Workstream 2 bounded B1 checkpoint
Observed path: `primary`
Observed result: `success`

## Outcome

The API factory is no longer a singleton reset function:

1. every `create_api_app(...)` call returns a new FastAPI object;
2. each created app owns a distinct `ApiRuntimeContainer`, project root,
   decision node, runtime state, runtime host, engine, outbound-policy snapshot,
   lazy stream/interaction/extension owners, and tracked task set;
3. HTTP, websocket, and lifespan execution resolve owners through the active
   ASGI app;
4. closing one created app does not close or replace another app's owners;
5. lifespan teardown cancels tracked tasks and closes the app-owned engine
   idempotently;
6. repeated construction and teardown leaves every observed container closed
   with zero tracked background tasks;
7. module-default owner aliases remain compatibility-only and cannot cross into
   factory-created apps.

This is a bounded B1 checkpoint, not completion of all Workstream 2 acceptance
gates. The compatibility default app/aliases and interface-owned outward
service/store factories remain B2 debt.

## Requirement Trace

| Trace | Required B1 behavior | Result |
|---|---|---|
| `ATAPI-B1-01` | New FastAPI identity per factory call | live subprocess and integration proven |
| `ATAPI-B1-02` | Distinct per-app runtime owner graphs | integration proven |
| `ATAPI-B1-03` | Concurrent requests retain their app root | integration proven |
| `ATAPI-B1-04` | Closing app A does not change app B | integration proven |
| `ATAPI-B1-05` | Engine and tracked tasks close once | integration proven |
| `ATAPI-B1-06` | Repeated lifecycles leave no tracked tasks | integration proven |
| `ATAPI-B1-07` | Default compatibility aliases do not cross apps | contract proven |
| `ATAPI-B1-08` | Baseline fails unless isolation observations are true | isolated-subprocess probe proven |

## Behavioral Proof

Routine proof set `ORKET_DISABLE_SANDBOX=1`.

1. B1-focused interface/runtime/live envelope:
   - command:
     `pytest tests/interfaces tests/runtime/test_startup_security_config.py tests/live/test_companion_voice_truth_live.py tests/scripts/test_build_architectural_truth_baseline.py -q`
   - result: `392 passed, 3 skipped`;
   - exit: `0`;
   - proof type: integration, contract, and local process behavior.
2. Canonical suite:
   - command: `python -m pytest -q`;
   - final result: `4392 passed, 53 skipped, 2 warnings`;
   - duration: `585.25s`;
   - exit: `0`;
   - proof type: repository-wide automated behavior.
3. Initial canonical attempt:
   - same command and environment;
   - result: tool timeout after `604s`, exit `124`, with no pytest failure output;
   - classification: environment/time-window blocker for that attempt, not a
     test pass or failure;
   - correction: reran the exact command with a larger execution window, which
     produced the successful terminal result above.

The two warnings are unchanged deprecation/runtime warnings in
`test_board_hierarchy_integrity.py` and `test_extension_runtime_service.py`.

## Baseline Proof

The stable architectural-truth baseline was regenerated after B1:

1. `collection_ok=true`;
2. `release_ready=false`;
3. API factory proof path is `primary`, result is `success`;
4. `same_app_object=false`;
5. `first_context_replaced=false`;
6. both configured roots are retained;
7. contexts, engines, and runtime states are distinct;
8. the module-default context is unchanged by factory calls;
9. all observed command behaviors remain successful;
10. the diff ledger contains seven rerun entries.

The baseline remains deliberately non-green for known debt:

1. 16 architecture exceptions remain;
2. package-only `orket/` Ruff inventory: 130 findings;
3. repository-root Ruff inventory: 1,631 findings;
4. 3,344 of 4,137 tests are unrecognized by the legacy taxonomy checker;
5. 76 Python files exceed 400 lines;
6. 237 functions exceed 70 lines;
7. the no-op checker reports 15 findings.

## Governance Proof

1. Changed-file Ruff:
   - result: pass;
   - exit: `0`.
2. Dependency direction:
   - command:
     `python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail`;
   - result: pass;
   - exit: `0`.
3. Documentation project hygiene:
   - result: pass;
   - exit: `0`.
4. `git diff --check`:
   - result: pass with existing line-ending warnings;
   - exit: `0`.

## Architecture Compliance Checklist

| Check | Result | Evidence |
|---|---|---|
| `AC-01` dependency direction | pass | strict legacy dependency gate passes |
| `AC-02` decision-node purity | partial / unchanged | per-app nodes are distinct, but registry construction remains in the interface composition module |
| `AC-03` explicit input contracts | pass | project root and target app are explicit at composition/lifecycle boundaries |
| `AC-04` deterministic runtime inputs | pass / unaffected | no new clock, randomness, or identity source |
| `AC-05` side-effect ownership | partial improvement | engine/tasks are app-container-owned; outward service/store factories remain B2 |
| `AC-06` adapter classification | partial / unchanged | outward store construction remains interface-owned |
| `AC-07` runtime truth claims | pass | concurrency, close isolation, teardown, baseline, and canonical suite are observed |
| `AC-08` observability authority | pass / unaffected | no event schema authority changed |
| `AC-09` replayability evidence | pass / unaffected | no replay contract changed |
| `AC-10` authority drift control | pass | delta, authority, architecture, roadmap, plan, register, baseline, tests, and proof align |

## Not Verified

1. Live network/provider behavior; B1 changes only local API composition and
   lifecycle ownership.
2. Durable outward store/service isolation between concurrent apps.
3. Extension-owned client/resource close behavior beyond the B1 engine and
   tracked task set.
4. Removal of the module-default app, aliases, or eager import-time engine.
5. Repo-wide Ruff success, strict taxonomy success, or zero no-op findings.
6. A version bump, commit, tag, or released package; none was requested.

## Remaining Blockers or Drift

1. `AT-EX-002` is narrowed but active: same-object factory behavior is fixed;
   default compatibility ownership and outward service/store isolation remain.
2. `AT-EX-003` remains active: `orket/interfaces/api.py` still composes decision
   nodes, orchestration owners, adapters, and outward services.
3. Workstream 2 gates forbidding interface-constructed runtime owners and
   module-global mutable aliases remain open for B2.
4. Package-only and repository-root Ruff inventories remain red at 130 and
   1,631 findings respectively.
5. Taxonomy, no-op, size, and authority-generation self-deception debt remains
   recorded in `AT-EX-013` through `AT-EX-016`.

## Exact Files Touched

1. `orket/application/services/api_runtime_container.py`
2. `orket/interfaces/api_runtime_context.py`
3. `orket/interfaces/api.py`
4. `orket/interfaces/routers/streaming.py`
5. `tests/conftest.py`
6. `tests/interfaces/conftest.py`
7. `tests/interfaces/test_api.py`
8. `tests/interfaces/test_api_card_authoring.py`
9. `tests/interfaces/test_api_composition_isolation.py`
10. `tests/interfaces/test_api_expansion_gate.py`
11. `tests/interfaces/test_api_flow_authoring.py`
12. `tests/interfaces/test_api_operator_views.py`
13. `scripts/governance/build_architectural_truth_baseline.py`
14. `tests/scripts/test_build_architectural_truth_baseline.py`
15. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_API_INSTANCES_B1_2026-07-30.md`
16. `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
17. `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`
18. `docs/projects/architectural-truth/architectural_truth_baseline.json`
19. `docs/projects/architectural-truth/API_INSTANCE_B1_PROOF_2026-07-30.md`
20. `docs/ARCHITECTURE.md`
21. `CURRENT_AUTHORITY.md`
22. `docs/ROADMAP.md`

Some listed files contained pre-existing user changes. B1 changed only bounded
hunks and did not overwrite unrelated work.
