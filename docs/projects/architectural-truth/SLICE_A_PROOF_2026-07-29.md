# Architectural Truth Slice A Proof

Date: 2026-07-29
Status: Historical implementation checkpoint; command-root status superseded
Observed path: `primary`
Observed result: `partial success`

Supersession note (2026-07-30): the command-root blocker and Workstream 1 status
below describe the 2026-07-29 observation. `orket runtime` is now the canonical
installed root and the current completion evidence is
`COMMAND_ROOT_PROOF_2026-07-30.md`. Other recorded debt remains active unless its
own authority says otherwise.

## Outcome

The bounded "Failure must fail" implementation is complete:

1. handled fatal CLI outcomes propagate a nonzero process status;
2. synchronous first-run setup no longer runs on the active event loop;
3. first-run success narration occurs only after settings persistence;
4. the governed-action quickstart supports help, scripted approval or denial,
   workspace selection, invalid input, and structured EOF refusal;
5. the governed-run default scenario is installed package data rather than a
   checkout-relative default;
6. the architectural baseline is stable, rerunnable, and explicitly distinguishes
   successful collection from release readiness.

The broader Workstream 1 and lane are not complete because the installed `orket`
command and source-only `python main.py` runtime remain separate roots, and the
repo-wide Ruff gate remains red.

## Requirement Trace

| Trace | Contract behavior | Result |
|---|---|---|
| `ATS-A-01` | Fatal/error-shaped CLI results return nonzero | implemented and live-proven |
| `ATS-A-02` | First-run persistence is event-loop safe | implemented and live-proven |
| `ATS-A-03` | First-run narration follows persistence | implemented and contract-proven |
| `ATS-A-04` | Quickstart help, scripted decisions, invalid input, and EOF are explicit | implemented and live-proven |
| `ATS-A-05` | Governed-run default is independent of caller CWD | implemented and installed-wheel-proven |
| `ATS-A-06` | Baseline and exception inventory are rerunnable and accountable | implemented and rerun-proven |
| `ATS-A-07` | One installed root owns the supported runtime | not implemented; `AT-EX-006` remains active |

## Changed Authority Edges

1. `main.py -> run_cli() -> integer exit code` now preserves handled failure status.
2. `run_cli() -> perform_first_run_setup()` now crosses an explicit worker-thread
   boundary around the synchronous settings/startup surface.
3. first-run persistence now precedes operator-facing success narration.
4. `orket-quickstart` now owns an argparse command contract with exit codes `0`,
   `1`, and `2`.
5. `orket demo governed-run` now resolves its default from
   `orket.quickstart/governed_run_scenario.yaml`.
6. architectural exception metadata now lives in
   `ARCHITECTURE_EXCEPTION_REGISTER.json`, while the generated observation
   baseline lives at one stable benchmark result path.

## Live Proof

Routine proof set `ORKET_DISABLE_SANDBOX=1`.

### Native source-process proof

| Scenario | Exit | Durable result |
|---|---:|---|
| fresh `python main.py --help` | `0` | first-run settings persisted |
| handled `extensions unsupported` failure | `1` | fatal output was not process success |
| first-run settings persistence failure | `1` | no first-run success narration |
| invalid named card | `1` | critical error was not process success |
| quickstart scripted approval | `0` | approved file and ledger written |
| quickstart scripted denial | `0` | file absent and denial ledger written |
| quickstart invalid input | `1` | file absent and invalid-input ledger written |
| quickstart EOF | `2` | structured input-required refusal; no traceback |
| governed-run default outside checkout | `0` | evidence bundle written |

### Built-wheel proof outside the checkout

A wheel installed into a temporary venv with host system packages available
imported Orket from that venv's `site-packages`, not the checkout. This proves the
wheel's entrypoints and package resource; it is not a dependency-isolated fresh
install. Observed results:

| Installed surface | Exit/result |
|---|---|
| `orket --help` | `0` |
| `orket-prompts --help` | `0` |
| `orket-quickstart --help` | `0` |
| `orket-quickstart --decision deny` | `0` |
| `orket demo governed-run` | `0` |
| installed package resource | present |
| governed-run evidence bundle | present |

The non-authoritative system-temp wheel/venv directory remains because the
execution environment rejected recursive cleanup outside the workspace. No
sandbox or cloud resources were created.

### Test and governance proof

1. Canonical test command:
   - command: `python -m pytest -q`
   - result: `4382 passed, 53 skipped, 2 warnings`
   - exit: `0`
2. Changed-file Ruff:
   - result: pass
   - exit: `0`
3. Documentation project hygiene:
   - result: pass
   - exit: `0`
4. Targeted documentation/governance tests:
   - result: `24 passed`
   - exit: `0`
5. Final focused Slice A tests:
   - result: `31 passed`
   - exit: `0`
6. `git diff --check`:
   - result: pass, with line-ending warnings only
   - exit: `0`

## Structural Proof

The stable baseline is
`docs/projects/architectural-truth/architectural_truth_baseline.json`. Its latest
rerun reports:

1. `collection_ok=true`;
2. `release_ready=false`;
3. seven command observations, all matching expected exit behavior;
4. false-success release blocker clear for the observed command set;
5. live API behavior still `same_app_object=true`;
6. 16 accountable active exceptions;
7. 130 repo-wide Ruff findings;
8. 3,339 of 4,127 tests unrecognized by the current taxonomy checker;
9. 76 Python files over 400 lines;
10. 237 functions over 70 lines;
11. 15 no-op findings, currently known to include type-only noise.

The baseline was executed repeatedly against the same path and appended diff-ledger
entries instead of creating timestamp-only outputs.

## Test Classification

1. `end_to_end`: native `main.py`, quickstart, and governed-run subprocess behavior.
2. `integration`: worker-thread startup and direct CLI/service composition behavior.
3. `contract`: persistence-before-narration and exception-register completeness.
4. `unit`: main crash handling and the outer interrupt-to-exit-130 boundary.

Temporary `Layer: live_truth` comments accompany the canonical
`@pytest.mark.end_to_end` markers because the current legacy taxonomy parser does
not recognize `end_to_end`. Removing that dual vocabulary is tracked by
`AT-EX-013`.

## Not Verified

1. A single installed root for both the card runtime and bundle tools; it does not
   exist yet.
2. A fully dependency-isolated clean install; the wheel probe used `--no-deps` and
   a venv with system site packages.
3. API app isolation or resource teardown; live proof confirms the current factory
   still returns the same app and replaces its context.
4. Repo-wide Ruff success; the observed result is failure with 130 findings.
5. Strict test-taxonomy success; the current checker remains incomplete and red.
6. Zero false positives from the no-op checker.
7. A patch version bump or release artifact; no release/commit was requested.

## Remaining Blockers or Drift

1. `AT-EX-002`: API factory singleton and orphaned-owner risk.
2. `AT-EX-006`: installed/source command-root split.
3. `AT-EX-001`: dependency checker enforces a weaker graph than the target architecture.
4. `AT-EX-004` and `AT-EX-005`: core effects and async-reachable synchronous I/O.
5. `AT-EX-013` through `AT-EX-016`: taxonomy, no-op, Ruff, and authority-snapshot debt.

The exact owner, reason, evidence, status, and removal condition for all active
exceptions are in `ARCHITECTURE_EXCEPTION_REGISTER.json`.

## Exact Files Touched

1. `main.py`
2. `pyproject.toml`
3. `README.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/ARCHITECTURE.md`
6. `docs/CONTRIBUTOR.md`
7. `docs/ROADMAP.md`
8. `docs/architecture/CONTRACT_DELTA_ARCHITECTURAL_TRUTH_SLICE_A_2026-07-29.md`
9. `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
10. `docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json`
11. `docs/projects/architectural-truth/SLICE_A_PROOF_2026-07-29.md`
12. `docs/projects/future/BRUTAL_CODE_REVIEW_ARCHITECTURAL_TRUTH_2026-07-29.md`
13. `docs/projects/future/BEHAVIORAL_REVIEW_ARCHITECTURAL_TRUTH_2026-07-29.md`
14. `docs/projects/architectural-truth/architectural_truth_baseline.json`
15. `orket/interfaces/cli.py`
16. `orket/discovery.py`
17. `orket/quickstart/governed_action_demo.py`
18. `orket/quickstart/governed_run_scenario.yaml`
19. `orket/application/services/governed_run_demo_service.py`
20. `scripts/governance/build_architectural_truth_baseline.py`
21. `scripts/governance/export_dependency_graph.py`
22. `tests/interfaces/test_cli_startup_semantics.py`
23. `tests/interfaces/test_cli_process_exit_semantics.py`
24. `tests/interfaces/test_governed_run_cli.py`
25. `tests/interfaces/test_api_composition_isolation.py`
26. `tests/quickstart/test_governed_action_demo.py`
27. `tests/scripts/test_build_architectural_truth_baseline.py`
28. `tests/platform/test_runtime_print_policy.py`
29. `tests/application/test_main_crash_handler.py`

Some listed files contained pre-existing user changes. Slice A changed only bounded
hunks in those files and did not overwrite unrelated work.
