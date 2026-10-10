# 0.8.1: governed reports and Gardener integration

Date: 2026-10-10

## What changed

PR #2 is accepted with modifications. The revised implementation uses the public
SDK submission, host-owned identity/timing and one `structured_report.v1`
verifier. Existing low-level submissions keep their completion policy. Run and
inspection output expose the retained advisory proposal.

The Gardener source example admits only report mode, selects bounded committed
Git blobs, includes explicit convention directories, rejects selected symlinks
and incomplete evidence, uses the canonical provider default, and settles native
child lifetimes before accepting output. It rechecks source state after inference.
Its successful result explicitly describes advisory delivery, not factual proof.
The independent report extension uses only the public SDK.

Review disposition:

- **Ship-risk debt resolved:** outside-root symlink reads, platform-dependent
  convention selection, swallowed Git failures, provider-default drift and
  unowned subprocess execution are replaced by explicit fail-closed boundaries.
- **Exploration-safe debt:** report-mode extensions remain trusted local Python;
  the wrapper is a source example, not a packaged Gardener entrypoint.
- **Self-deception debt avoided:** report shape/reference verification is not
  represented as proof of audit accuracy, full repository coverage or executed
  tests. Controlled provider responses are not represented as live model proof.

## What was verified

**Live proof: primary / success, native Windows.** Fresh source copies built core
0.8.1 and SDK 0.8.0 wheels. A fresh external environment installed both, passed
`pip check`, checked installed origins/namespace ownership and compared installed
package bytes with the wheels. The trusted report extension passed strict
validation and the normal Git extension installer.

Gardener's actual `run_command_harness`, without a substitute subprocess runner,
dispatched the copied source wrapper using that installed Python. Gardener was
clean at commit `551d19c4df73c1b41cffad3a3abb491fbe20d028`. The target and convention
Git repositories used native Windows paths with spaces and Unicode. Actual
llama.cpp inference returned a report identifying missing installation
instructions in the supplied sample README. Host verification accepted the
report, and its single model receipt recorded the exact selected model and
measured usage. Fresh-process inspection preserved final truth and the proposal;
replay matched. Both source repositories retained their commits and clean status.

The owned llama.cpp server settled using the Windows Job backend with complete
capture and confirmed cleanup; its port closed. A second actual Gardener dispatch
to the held unavailable endpoint returned a blocked failure, with no fallback.
Routine proof used `ORKET_DISABLE_SANDBOX=1`.

Machine evidence is retained locally at
`benchmarks/results/releases/0.8.1/gardener-integration.json` with the shared diff
ledger, source identity, wheel hashes, command lifetimes and temporary artifact
paths. This generated receipt is not a published or tracked artifact. The
authored source was frozen throughout the run. Subsequent changes were this
report, release documentation and removal of a trailing documentation blank line;
runtime, extension, wrapper and test bytes were unchanged.

**Targeted runtime/integration verification:** 132 distinct tests passed: 12
Gardener wrapper cases and 120 report admission/ownership, low-level submission,
CLI, loop, replay, terminal, API and provider-cleanup regressions. The wrapper
cases exercise real Git, native CLI/SDK children, SQLite and controlled HTTP;
negative controls cover write modes, symlinks, dirty/missing/oversized sources,
unavailable models, invalid reports and source mutation during inference.

**Structural verification:** canonical Ruff; targeted mypy on all ten affected
core modules; dependency direction with zero violations, cycles, unknown modules
or adapter-effect violations; authority render/check; documentation hygiene;
version/changelog alignment; whitespace checks. Strict test taxonomy collected
13,395 tests with no missing/invalid layers. Collection is not full-suite execution.
The authority checker reports `structural_authority_valid=true` and
`current_proof_established=false`; this scoped integration does not establish
portable whole-runtime proof. Architecture checklist AC-01 through AC-10 passes
within this change's scope: existing owners remain authoritative and the changed
boundary has a same-change durable contract and adverse-path evidence.

## What was not verified

- The complete Gardener `align` CLI, scheduling or overnight workflows. Proof
  reaches the real command-dispatch boundary used by those callers.
- Other operating systems/providers, hostile extension containment, arbitrary
  report accuracy, or repeated model reliability.
- The full 13,395-test suite or a new coverage measurement.
- Hosted Quality execution. The connected review service required a GitHub
  connection; local checks do not substitute for a hosted CI result.

## Remaining blockers or drift

No unresolved blocker remains for the bounded report-only adapter.

Gardener's separate Windows CLI `fcntl` dependency remains outside this patch.
The existing continuation policy can label invalid reports with the broader
`capability_budget_exhausted` reason when the zero effect budget takes precedence.
The detailed failure remains in retained result/model evidence and cannot
produce successful final truth. Neither limitation is hidden by a fallback.

## Exact repository files touched

- `.gitea/workflows/quality.yml`
- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `docs/CONTRIBUTOR.md`
- `docs/README.md`
- `docs/architecture/CONTRACT_DELTA_AGENT_TASK_SUBMISSION_2026-10-10.md`
- `docs/architecture/CONTRACT_DELTA_GARDENER_REPORT_HARNESS_2026-10-10.md`
- `docs/architecture/current_authority.json`
- `docs/guides/external-extension-authoring.md`
- `docs/releases/0.8.1/PROOF_REPORT.md`
- `docs/specs/GARDENER_REPORT_HARNESS.md`
- `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
- `docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md`
- `examples/gardener_harness/README.md`
- `examples/gardener_harness/gardener_harness.py`
- `examples/gardener_harness/gardener_snapshot.py`
- `examples/gardener_harness/gardener_submission.py`
- `examples/governed-report/README.md`
- `examples/governed-report/extension.yaml`
- `examples/governed-report/inputs.json`
- `examples/governed-report/report_agent.py`
- `examples/governed-report/submission.json`
- `orket/adapters/storage/governed_agent_task_inputs.py`
- `orket/application/services/governed_agent_execution_composition.py`
- `orket/application/services/governed_agent_inspection_service.py`
- `orket/application/services/governed_agent_loop_service.py`
- `orket/application/services/governed_agent_report_verifier.py`
- `orket/application/services/governed_agent_submission_service.py`
- `orket/application/services/governed_agent_task_service.py`
- `orket/extensions/governed_agent_catalog.py`
- `orket/extensions/models.py`
- `orket/interfaces/governed_agent_cli.py`
- `pyproject.toml`
- `tests/helpers/governed_agent_task.py`
- `tests/integration/test_gardener_harness_example.py`
- `tests/integration/test_governed_agent_task.py`
- `tests/integration/test_governed_agent_task_ownership.py`
