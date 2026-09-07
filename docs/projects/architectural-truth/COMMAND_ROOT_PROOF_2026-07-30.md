# Architectural Truth Command-Root Proof

Date: 2026-07-30
Status: Workstream 1 completion checkpoint
Observed path: `primary`
Observed result: `success`

## Outcome

The installed `orket` console script is now the one canonical operator root:

1. `orket runtime` starts the default card runtime;
2. `orket runtime --card <card_id>` reaches the existing card parser without a
   duplicate option implementation;
3. `orket --help` retains the existing bundle command tree and lists `runtime`;
4. first-run environment loading occurs before event-loop startup;
5. handled fatal and uncaught card failures propagate nonzero process status;
6. first-run and generated command suggestions name `orket runtime`;
7. `python main.py [runtime arguments]` remains an explicitly bounded source
   wrapper through `0.5.x`, with removal requiring an explicit `0.6.0` delta;
8. `main.py` delegates to `orket.cli:main` with the `runtime` prefix instead of
   retaining a second bootstrap or failure-mapping implementation.

The installed console-script target is `orket.cli:main`. That small package-level
module is the composition root. The bundle interface describes the `runtime`
subcommand for root help but does not import runtime/settings or own bootstrap.

## Requirement Trace

| Trace | Required behavior | Result |
|---|---|---|
| `ATCR-01` | One installed root exposes the supported runtime | implemented and wheel-proven |
| `ATCR-02` | Runtime arguments use the existing parser | contract- and process-proven |
| `ATCR-03` | Help names `orket runtime` and exposes `--card` | native-process- and wheel-proven |
| `ATCR-04` | Fresh first run persists before runtime execution | native-process- and wheel-proven |
| `ATCR-05` | Handled fatal and invalid-card paths return nonzero | native-process- and wheel-proven |
| `ATCR-06` | Existing non-runtime bundle commands remain reachable | contract- and root-help-proven |
| `ATCR-07` | Source compatibility has an explicit removal boundary | contract- and authority-recorded |
| `ATCR-08` | Source compatibility delegates to the installed root | unit-, process-, and canonical-suite-proven |

## Live Installed-Wheel Proof

Routine proof set `ORKET_DISABLE_SANDBOX=1`. A new `0.5.9` wheel was built, installed
with `--no-deps` into a venv with system site packages, and invoked from a directory
outside the checkout. The package imported from that venv's `site-packages`.

| Observation | Result |
|---|---|
| wheel console entrypoint | `orket.cli:main` |
| `orket --help` | exit `0`; lists `runtime` |
| `orket runtime --help` | exit `0`; usage is `orket runtime`; exposes `--card` |
| fresh settings | persisted under the isolated durable root |
| `orket runtime extensions unsupported` | exit `1`; error names `orket runtime extensions list` |
| invalid named card | exit `1`; outer boundary emits `[CRITICAL ERROR]` |

This is live installed-package behavior, but it is not a fully dependency-isolated
fresh-install proof because the venv used system site packages and the wheel was
installed with `--no-deps`.

## Test and Governance Proof

1. Final canonical suite:
   - command: `python -m pytest -q`
   - result: `4388 passed, 53 skipped, 2 warnings`
   - exit: `0`
2. Initial canonical attempt:
   - result: `4387 passed, 53 skipped, 2 warnings, 1 failed`
   - cause: the new package-level CLI root was absent from the explicit runtime
     `print()` allowlist;
   - correction: `orket/cli.py` was added as an intentional command-line surface;
   - focused rerun: `10 passed`.
3. Changed-file Ruff:
   - result: pass;
   - exit: `0`.
4. Dependency direction:
   - command:
     `python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail`
   - result: pass;
   - exit: `0`.
5. Documentation project hygiene:
   - result: pass;
   - exit: `0`.
6. Authority/document targeted tests:
   - result: `13 passed`;
   - exit: `0`.
7. `git diff --check`:
   - result: pass with existing line-ending warnings;
   - exit: `0`.

## Architectural Baseline

The stable baseline at `architectural_truth_baseline.json` was rerun after the
composition-root correction:

1. `collection_ok=true`;
2. `release_ready=false`;
3. seven live command observations all succeeded;
4. the false-success release blocker is clear for the observed commands;
5. 16 accountable architecture exceptions remain;
6. package-only `orket/` Ruff inventory: 130 findings;
7. repository-root Ruff inventory: 1,635 findings;
8. test taxonomy: 3,339 of 4,133 tests are unrecognized by the legacy checker;
9. 76 Python files exceed 400 lines;
10. 237 functions exceed 70 lines;
11. the no-op checker reports 15 findings;
12. the baseline diff ledger contains six rerun entries.

The package-only and repository-root Ruff counts are intentionally distinguished;
neither is presented as green.

## Architecture Compliance Checklist

| Check | Result | Evidence |
|---|---|---|
| `AC-01` dependency direction | pass | package-level composition root, delegating source wrapper, strict legacy dependency gate passes |
| `AC-02` decision-node purity | pass / unaffected | no decision node changed |
| `AC-03` explicit input contracts | pass | runtime parser receives an explicit argument vector |
| `AC-04` deterministic runtime inputs | pass / unaffected | no decision time, randomness, or identity source added |
| `AC-05` side-effect ownership | pass | process bootstrap remains at the composition boundary |
| `AC-06` adapter classification | pass / unaffected | no adapter changed |
| `AC-07` runtime truth claims | pass | native and wheel failure/status proof |
| `AC-08` observability authority | pass / unaffected | no event schema changed |
| `AC-09` replayability evidence | pass / unaffected | no replay contract changed |
| `AC-10` authority drift control | pass | authority, contributor, runbook, README, roadmap, delta, plan, and tests updated together |

## Not Verified

1. A dependency-isolated install that resolves and installs every declared
   dependency from an empty environment.
2. API instance isolation or resource teardown; that is Slice B.
3. Repo-wide Ruff success, strict taxonomy success, or zero no-op false positives.
4. A patch version bump, commit, tag, or released package; none was requested.

## Remaining Blockers or Drift

1. `AT-EX-002`: `create_api_app()` still has singleton/context-replacement behavior.
2. `AT-EX-001`, `AT-EX-004`, and `AT-EX-005`: dependency-policy, core-effect, and
   async-reachable synchronous-I/O debt remain.
3. `AT-EX-006` is narrowed to the approved `0.5.x` source-wrapper compatibility
   window; it is no longer a split canonical-root exception.
4. `AT-EX-013` through `AT-EX-016`: taxonomy, no-op, Ruff, and authority-generation
   debt remain active.
5. The verified proof directory
   `C:\Source\Orket\.tmp\orket-command-root-proof-11ecb299b7af49ad94c5150c1ae4a419`
   remains because the execution policy rejected recursive cleanup after an
   explicit containment check. It is workspace-local and ignored, but not
   represented as cleaned up.

## Exact Files Touched

1. `pyproject.toml`
2. `orket/cli.py`
3. `orket/interfaces/cli.py`
4. `orket/interfaces/orket_bundle_cli.py`
5. `orket/discovery.py`
6. `scripts/governance/build_architectural_truth_baseline.py`
7. `tests/application/test_discovery_engine_recommendations.py`
8. `tests/interfaces/test_cli_process_exit_semantics.py`
9. `tests/interfaces/test_cli_startup_semantics.py`
10. `tests/interfaces/test_orket_bundle_cli.py`
11. `tests/platform/test_runtime_print_policy.py`
12. `README.md`
13. `CURRENT_AUTHORITY.md`
14. `docs/CONTRIBUTOR.md`
15. `docs/RUNBOOK.md`
16. `docs/guides/examples.md`
17. `docs/ROADMAP.md`
18. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_COMMAND_ROOT_2026-07-30.md`
19. `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
20. `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`
21. `docs/projects/architectural-truth/architectural_truth_baseline.json`
22. `docs/projects/architectural-truth/COMMAND_ROOT_PROOF_2026-07-30.md`
23. `main.py`
24. `tests/application/test_main_crash_handler.py`
25. `docs/ARCHITECTURE.md`
26. `docs/projects/architectural-truth/SLICE_A_PROOF_2026-07-29.md`

Some listed files contained pre-existing user changes. This checkpoint changed
only bounded hunks and did not overwrite unrelated work.
