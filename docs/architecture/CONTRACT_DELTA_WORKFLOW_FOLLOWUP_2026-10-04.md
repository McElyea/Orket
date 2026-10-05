# CLI benchmark acceptance and operator truth disclosure

Owner: Orket Core
Date: 2026-10-04
Effective patch: 0.7.6

## Delta

The benchmark adapter now admits declared CLI examples as well as function
examples. CLI admission requires a retained implementation inventory and exact
stdout/stderr/exit expectations. The existing card acceptance service owns
snapshot execution and process cleanup; there is no new completion authority.
The adapter's private module/function names change from `function_acceptance` /
`declare_function_acceptance` to `task_acceptance` / `declare_task_acceptance`.
No compatibility shim is introduced. The v2 CLI bank now declares a two-file
implementation layout and corrects nine tasks' accidentally escaped line endings.
Historical benchmark results keep their original input identity.

The required Python main guard now uses top-level AST equality rather than a
quote-sensitive substring. Equivalent quotes/operand order pass; comments,
strings, nested guards and invalid syntax do not. Other token checks are unchanged.
Historical verdicts are retained when corrected scoring is reported separately.

CLI benchmarks supply a support-verifier command and assertions from the first
declared case, preventing the default no-argument invocation from rejecting a
valid argument-taking CLI. Mandatory completion acceptance still checks all cases.
The preparer previously wrote a lower-precedence organization file. It now updates
the modular architecture policy actually loaded by the runtime and captures the
canonical organization name; original failed configurations remain evidence.

The sanity workflow gains bounded inputs and one declared file-write receipt.
It does not establish general system health. Preparation and supported benchmark
shapes remain defined by `docs/specs/WORKFLOW_BENCHMARK_READINESS.md`.

Run history/detail read models now disclose retained packet-1 repairs and
nonconformance in both machine-readable `runtime_truth` and human summaries.
The application projects supplied evidence; the interface renders it. No read
changes retained facts, acceptance, classification, conformance or lifecycle.
Missing evidence does not acquire a positive verdict. Surface authorities are
`docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md` and `docs/API_FRONTEND_CONTRACT.md`.

Contributor distribution builds now require a fresh source tree without a reused
build cache, wheel namespace inspection and affected installed-entrypoint proof
outside the checkout. A failed candidate exposed stale SDK files in the core
wheel despite passing dependency metadata checks. This adds verification discipline
without changing SDK ownership, dependency pins or accepted published artifacts.

## Validation and migration

Native acceptance tests must reject wrong output, missing modules and literal
backslash-n output while preserving valid stdout/stderr/exit behavior and replay.
Run actual CLI benchmarks and the prepared sanity workflow on the selected
Windows llama.cpp provider. Exercise operator disclosure through the real API,
in addition to contract controls. Final proof and limits belong in the 0.7.6
release report. Do not infer full model endurance or benchmark quality from setup.

Benchmark consumers must use the corrected task identity and declared inventory;
internal adapter importers must update names. Operator clients may render the
additive truth block and warnings without changing completion logic. Revert any
demonstrated regression through a new patch; never overwrite historical evidence.
PRR remains closed, with PRR-S1 and broader architecture work deferred.
