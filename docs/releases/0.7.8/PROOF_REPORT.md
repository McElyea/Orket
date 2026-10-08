# Core 0.7.8 publication preparation

Date: 2026-10-07
Status: Windows quality and installed gates passed; main publication authorized
Acceptance platform: native Windows, Python 3.11.14

## What changed

Guided local setup, diagnostics, the governed local-agent example, hardware
observation and candidate/process/Mac acceptance tools are prepared. Native Mac
ownership remains unimplemented; this candidate does not declare Mac support
complete. The active queue remains
`docs/projects/macos-support/MACOS_SUPPORT_IMPLEMENTATION_PLAN.md`.

Quality investigation found synchronous included-route dependency construction
on the first FastAPI request. Startup now owns the captured public schema callback
before engine initialization/readiness. Request timing and cancellation assertions
are unchanged. The task registry's mypy error is corrected with a type annotation;
the print policy distinguishes actual AST calls from embedded child-script text.
Required contracts and current authority are updated.

The unrelated stored workflow recovery was already completed and archived under
`docs/projects/archive/architectural-truth/WR10052026/WORKFLOW_RECOVERY_PLAN.md`.
All 38 retained recovery process receipts are terminal. Its unsupported assets
remain quarantined, and six tasks' retained model failures are not sampled until
green or mislabeled as unfinished implementation. Its historical source-bound
provider observations keep their original scope.

## What was verified

- Native Windows scoped regression: 63 tests passed, including first-request replay
  ownership, held schema cancellation/native failure, real server bootstrap/reload
  and task registry lifecycle. Retained receipt:
  `C:/Users/jonmc/AppData/Local/Temp/orket-prepublish-o722qmcu/receipt.json`.
- Additional native callback capture and instrumented cold-request controls passed.
  Before correction: 354 dependency constructions, 0.1678s included-route compilation.
  After correction: no request-side dependency constructions, cached route traversal
  0.0004704s, replay admission 0.01539s and total responsiveness 0.02417s against
  the original 0.5s assertion. These scoped instrumented observations are not a
  performance benchmark or reconstruction of the original 0.6115s scheduler state.
  Historical native profile retained at `orket-prepublish-nse9xebs`; final profile
  at `.tmp/macos-support/replay-call-profile.json` and its JUnit/prof files.
- Canonical mypy (1,232 source files), Ruff, project hygiene, authority validation/
  generated equality, dependency enforcement, strict taxonomy, critical no-op,
  template synchronization, core version/changelog policy and diff whitespace
  checks passed. Retained receipt:
  `C:/Users/jonmc/AppData/Local/Temp/orket-prepublish-nxz8zhpk/receipt.json`.
  Governance proof is structural; current-authority runtime proof remains false.

- Fresh installed core 0.7.8/SDK 0.7.2 candidate: 22 commands passed, checking
  1,251 core and 31 SDK files against the built wheels. Core SHA256:
  `48c0cac327120e2f76497ea520f75550019734736ed653956f77df5e0748c042`;
  SDK SHA256: `5b8835724e75ce7fd2ee427fac976303e782ea824e7f38f00409256774e1a18e`.
  Retained external receipt: `orket-candidate-zqyfte2g/receipt.json` under the
  Windows Temp root above. All 27 installed process controls passed at
  `orket-native-process-3lj4ma91/receipt.json` (five owned commands).
- Actual installed llama.cpp workflow and guided setup passed at
  `orket-mac-acceptance-qxkdphe1/receipt.json` (18 owned commands). Six measured
  model calls, 754 input/378 output tokens, two iterations, final ticket counts
  open=2/closed=2/blocked=1. Fresh inspect/replay preserved the database bytes;
  actual missing-provider connection refusal and closed resources were checked.
  Native server cancellation, complete capture and closed port were confirmed.
  Eight Windows MA controls passed; MA-05 stayed BLOCKED. Combined attribution is
  CONTROL_PASS/primary/partial success, with Mac completion false.
- Canonical full coverage: `pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89`.
  **13,252 passed, 93 skipped, three pytest warnings, 89.25% in 5,681.17s**.
  Path/result: primary/success, live native Windows execution. Retained receipt:
  `C:/Users/jonmc/AppData/Local/Temp/orket-prepublication-coverage-a_vwn_7a/receipt.json`.
  Native Job capture/cleanup confirmed; runner, transport, supervisor and test
  processes were absent afterward. The original responsiveness assertion and
  coverage floor were unchanged. The original failed full receipt remains at
  `orket-mac-coverage-_yxrz380/receipt.json`; it is not rewritten as passing proof.
- The installed chain, whole-suite campaign and independent audits shared frozen
  authored source SHA256 `a257deef31d2f4b8c9ba916767596d7a2ad71d190985dce5a092091424c36d48`
  (5,192 Git-visible paths). `.tmp/macos-support/prepublish-audit.json` and
  `prepublish-coverage-audit.json` checked 106 command-log hashes, candidate byte
  identity, retained effects/JUnit, measurement and settlement. Canonical package,
  process, native and full coverage JSON reports retain these terminal runs.
  Subsequent changes only close out documentation; tested runtime/package bytes
  remain unchanged. Full proof is historical source-bound evidence at that snapshot,
  not a claim that the later checkpoint has the same whole-repository digest.
- Local version observation found ignored checkout-root `orket.egg-info` still
  reporting 0.7.7 after pip successfully installed 0.7.8. That stale generated
  metadata was retained at `.tmp/macos-support/stale-orket-0.7.7.egg-info` before
  full coverage. The selected runtime then reported 0.7.8; no dependency upgrade
  or authored package source change was needed.

The three pytest warnings concern TestClient dependency deprecation, the deliberate
legacy-domain import and the low-token provider request control. Coverage separately
reported one incomplete 16,384-byte worker SQLite file. Read-only inspection found
only empty `coverage_schema` and `meta` tables, no populated schema-version row and
no file/arc data. Its SHA256 is
`93ea186133c8a4bd1ddee25cb8e1ee649318ce609fd5737e7678dd13fe60d548`.
The file remains retained; it was neither deleted nor repaired to quiet the warning.
The full gate passed without that worker measurement. The audit records its exact
path and the combined measurement's identity; missing worker coverage is disclosed.

Architecture review: AC-01 through AC-10 pass for the changed startup/type slice.
The interface supplies a captured public callback; the application retains native
preparation, failure and cleanup authority. No decision node, adapter classification,
wire/event schema or replay mutation changed. Dependency enforcement, actual native
settlement/refusal controls and updated contracts support this bounded assessment;
it does not retire pre-existing whole-repository architecture exceptions.

After the documentation closeout, project hygiene, authority validation/generated
equality, install-surface convergence, core release policy, documentation regressions,
canonical mypy/Ruff and diff whitespace checks passed again. Receipt:
`C:/Users/jonmc/AppData/Local/Temp/orket-prepublish-closeout-nnynbab0/receipt.json`;
canonical `.tmp/macos-support/prepublish-closeout.json`. All 1,289 tested package
input hashes remained unchanged. No broader live rerun is inferred from these
structural/doc controls. Only this evidence paragraph followed that check group.

## What was not verified

Native macOS/Metal, Python 3.12, alternate platform/hosted Quality execution,
declared skips and live Docker acceptance are not verified by this preparation.
The Mac tester is a future access path; signing/entitlement feasibility and all
MA-01 through MA-09 still require native proof. No new model benchmark sweep,
semantic determinism or whole architectural-truth lane closure is claimed.

## Remaining blockers or drift

Windows quality and installed proof permit publication of this preparation candidate.
The user explicitly authorized committing the reviewed aggregate on main, creating
annotated tag `v0.7.8` and pushing both. Remote branch/tag refs establish publication
state; this report records pre-publication evidence and does not close the Mac lane.
Native ownership/access and all required Mac acceptance remain blocking that lane.

Archived workflow limits remain: the scorer's historical `input_report` label uses
the task-bank path; identify actual input through its wrapper/raw receipt. The
operator-owned skip-worktree workflow override remains preserved. Retained packet
conformance warnings and wrong model outputs grant no completion authority.

## Exact files touched

The complete approved aggregate is in [CHANGED_FILES.md](CHANGED_FILES.md), including
the pre-existing workflow recovery, Mac work, quarantine moves and this quality
slice. Ignored evidence and external candidate environments are not source changes.
