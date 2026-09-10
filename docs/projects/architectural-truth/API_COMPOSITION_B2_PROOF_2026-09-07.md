# Architectural Truth API Composition B2 Proof

Date: 2026-09-07
Status: Workstream 2 complete; Slice B2 implemented
Observed path: `primary`
Observed result: `success`
Proof classification: integration, contract, structural, and local subprocess

## Outcome

Slice B2 removes the last shared API runtime owner and moves the complete graph
behind one application-owned factory:

1. importing `orket.interfaces.api` constructs no FastAPI app or runtime owner;
2. the compatibility `app` and mutable owner aliases are removed;
3. each `create_api_app(...)` result owns distinct engine, runtime state/event
   queue, stream bus, interaction manager, extension owners/catalog, outward
   stores/services, root, and policy snapshot, plus an app-container-held
   model-selector factory;
4. `orket.interfaces.api` constructs no protected application, adapter,
   decision-node, kernel, extension, or orchestration implementation class;
5. request and websocket callbacks resolve only the active app's context;
6. lifespan teardown closes the selected app without changing a peer app;
7. tests, governance probes, and baseline collection now retain factory-created
   apps or pass explicit roots instead of relying on a hidden default owner.

The removal condition for `AT-EX-002` is satisfied and the exception is removed.
Broader interface transport/facade extraction remains separately tracked by
`AT-EX-003`.

## Requirement Trace

| Trace | Required B2 behavior | Result |
|---|---|---|
| `ATAPI-B2-01` | Module import creates no app/runtime owner | isolated-subprocess contract proof passed |
| `ATAPI-B2-02` | No protected implementation is constructed in the API router module | AST structural contract proof passed |
| `ATAPI-B2-03` | Stores/services are application-container-owned | integration proof passed |
| `ATAPI-B2-04` | Apps own distinct stores, event queues, settings, and extension catalogs | integration proof passed |
| `ATAPI-B2-05` | Concurrent requests retain their own roots | integration proof passed |
| `ATAPI-B2-06` | One-app close and repeated teardown leak no tracked task | integration proof passed |
| `ATAPI-B2-07` | Production server retains a factory-created app | interface entrypoint proof passed |
| `ATAPI-B2-08` | Baseline observes isolation and no default owner | live isolated-subprocess probe passed |

## Behavioral Proof

Routine proof set `ORKET_DISABLE_SANDBOX=1`.

1. Complete interface suite:
   - command: `python -m pytest -q tests/interfaces`;
   - observed result before the final added structural assertion: `387 passed`;
   - the final structural assertion is included in the canonical result below;
   - proof type: integration and contract.
2. Corrected governance-probe regression set:
   - command:
     `python -m pytest -q tests/scripts/test_check_ui_lane_security_boundary_tests.py tests/scripts/test_run_runtime_truth_acceptance_gate.py`;
   - observed result: `59 passed in 53.88s`;
   - proof type: integration and local script behavior.
3. Canonical repository suite on the final source state:
   - command: `python -m pytest -q`;
   - observed result: `4507 passed, 55 skipped, 2 warnings in 495.40s`;
   - exit: `0`;
   - proof type: repository-wide automated behavior.
4. Initial canonical attempt:
   - same command and environment;
   - observed result: `57 failed, 4450 passed, 55 skipped, 2 warnings`;
   - cause: one standalone UI security probe invoked an API path validator
     without the default app removed by B2;
   - correction: the validator accepts an explicit root and the governance
     probe supplies a temporary root. The 59-test regression set and complete
     canonical rerun both pass.

The two warnings are unchanged: the deprecated `orket.domain` import warning in
`test_board_hierarchy_integrity.py` and the governed-output token warning in
`test_extension_runtime_service.py`.

## Baseline Proof

The stable architectural-truth baseline was regenerated after B2:

1. `collection_ok=true`;
2. `release_ready=false` for explicitly retained repository debt;
3. API factory path is `primary`, result is `success`;
4. `same_app_object=false` and `first_context_replaced=false`;
5. both roots are retained and contexts, engines, and runtime states are distinct;
6. `module_default_owner_absent=true`;
7. active exception count is reduced from 16 to 15;
8. `AT-EX-002` is absent from the generated snapshot.

## Governance Proof

1. Touched-path Ruff: pass.
2. Focused mypy with external imports skipped: pass for the three B2 production
   modules.
3. Dependency direction with strict legacy-edge enforcement: pass.
4. Documentation project hygiene: pass.
5. Strict governed-agent docs lint: pass.
6. Strict architectural-truth docs lint: pass after registering the active lane
   docs and aligning the historical quickstart EOF reference with its contract.
7. New production file size and touched-function size: pass.
8. `git diff --check`: pass aside from line-ending conversion warnings.

## Not Verified

1. Live external network or model-provider behavior; B2 changes composition and
   lifecycle ownership, not provider behavior.
2. Hostile extension isolation; the existing trusted subprocess boundary is
   unchanged.
3. Production governed-agent supervisor activation was outside the B2 proof
   boundary; Slice 6B subsequently composed and deterministically proved that
   dispatcher/capacity/API lifecycle path.
4. Repository-wide Ruff, strict taxonomy, no-op, size, or complete architecture
   release readiness; the baseline remains deliberately non-green.
5. A version bump, commit, tag, push, or released package; none was requested for
   this slice.

## Remaining Blockers or Drift

1. `AT-EX-003` remains active for broader interface transport/facade extraction.
2. Slice C must ratify and enforce one normative dependency-layer manifest.
3. The remaining 15 architectural exceptions and baseline-reported lint,
   taxonomy, no-op, and size debt remain assigned to their existing workstreams.

## Exact Files Touched

The B2-specific implementation and authority files are:

1. `orket/application/services/api_runtime_composition.py`
2. `orket/application/services/api_runtime_container.py`
3. `orket/interfaces/api.py`
4. `scripts/governance/build_architectural_truth_baseline.py`
5. `scripts/governance/check_ui_lane_security_boundary_tests.py`
6. `tests/conftest.py`
7. `tests/interfaces/conftest.py`
8. `tests/interfaces/test_api_composition_isolation.py`
9. `tests/interfaces/test_api_task_lifecycle.py`
10. migrated API tests that previously patched module owners
11. `tests/scripts/test_build_architectural_truth_baseline.py`
12. `tests/application/test_runtime_state_fixture_lint.py`
13. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_API_COMPOSITION_B2_2026-09-07.md`
14. `docs/projects/architectural-truth/README.md`
15. `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
16. `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`
17. `docs/projects/architectural-truth/architectural_truth_baseline.json`
18. `docs/projects/architectural-truth/API_COMPOSITION_B2_PROOF_2026-09-07.md`
19. `docs/ARCHITECTURE.md`
20. `CURRENT_AUTHORITY.md`
21. `docs/ROADMAP.md`
22. governed-agent current authority docs updated to mark B2 cleared

Slice 6A files remain part of the same uncommitted working tree from the prior
slice and are not reclassified as B2 implementation.
