# Release `0.6.2` Proof Report

Date: `2026-09-11` (America/Denver). Owner: `Orket Core`.
Git tag: `v0.6.2` (annotated, on the release commit).
Policy: [core versioning](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md).
Checklist: [release gates](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md).

## Summary of Change

Release the shared llama.cpp defaults, exact Qwen3.8 profile promotion, native
render/token verification, cache-enabled b10809 operator setup, stronger audit
and promotion gates, corrective-prompt diagnostics and truthful empty replay.
The updated architectural-truth plan is retained as remaining work. Detailed
implementation proof and the completed promotion lane are linked from the
[candidate report](docs/architecture/LLAMA_CPP_QWEN38_PROMOTION_VERIFICATION_2026-09-11.md).

This is the required patch step for committing the completed candidate to main.
The earlier user-authorized minor releases remain core/SDK 0.6.0 and reference
extension 0.2.0. SDK and extension runtime code do not change in this patch.
The release tag binds the final source; historical candidate reports retain
their original 0.6.1-based wheel identity and pre-publication statements.

## Stability Statement

The supported claim is the documented bounded trusted-extension agent loop on
the exact promoted llama.cpp profile. Core owns authorization, budgets, effects,
recovery and final truth. The reference verifier remains ticket-report-specific.
Other providers require explicit selection and retain their own admission gates.
No production soak, arbitrary coding-objective verification, hostile-code
containment, distinct-model capacity or broader model-family promotion is claimed.

## Compatibility Classification

- `compatibility_status`: `breaking`
- `affected_audience`: `operator_only`
- `migration_requirement`: `required`

The operator-visible default changes to llama.cpp. No database migration or
public SDK protocol change is introduced. Stored run configurations remain
immutable. SDK 0.6.0 is additionally verified against this exact core 0.6.2
artifact with reference extension 0.2.0; this does not admit untested versions.
The source wrapper and hidden `--rock` alias retain their existing 0.6.x contract.

## Required Operator or Extension-Author Action

Follow the [runbook](docs/RUNBOOK.md#governed-agent-bounded-cli) to launch upstream
llama.cpp `b10809-5266f24da` with the exact Qwen3.8 Q4_K_L weights, served alias,
8192-token context, `--jinja --reasoning off --cache-prompt --cache-ram 8192`,
and the core-packaged `qwen38_text_chatml.jinja`. The template is 230 bytes with
SHA256 `8fc57a9f65eaaaee48e80771aea4775f7d3a8adb466a6193d8de551fa124d578`.
Select `lmstudio` or `ollama` explicitly when intended. Server unavailability
must never trigger a provider switch.

Install the core 0.6.2 wheel with SDK 0.6.0 and run `python -m pip check`.
For historical SDK-bundling core upgrades, supply both pinned wheels and
force-reinstall SDK last as documented in
[SDK versioning](docs/requirements/sdk/VERSIONING.md). Strictly validate the
extracted reference extension 0.2.0 source distribution before host intake.

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason / Observed Path | Evidence |
| --- | --- | --- | --- | --- | --- |
| Installed `orket runtime` startup and quit | default_runtime_entrypoint | live | success | Existing reconciliation warning / degraded | [surfaces](benchmarks/results/releases/0.6.2/surfaces.json) |
| `python server.py` and real HTTP health request | api_runtime_entrypoint | live | success | None / primary | [surfaces](benchmarks/results/releases/0.6.2/surfaces.json) |
| Packaged governed-run demo and durable evidence | workflow_path | live | success | None / primary | [surfaces](benchmarks/results/releases/0.6.2/surfaces.json) |
| Installed staged agent, approvals and process recovery | workflow_path | live | success | None / primary | [acceptance](benchmarks/results/releases/0.6.2/acceptance.json) |
| llama.cpp, subprocess broker, SQLite and file effects | integration_route | live | success | None / primary | [acceptance](benchmarks/results/releases/0.6.2/acceptance.json) |
| Streaming, ODR, generation and discovery | integration_route | live | success | Source runtime unchanged by release metadata / primary | [source integration](benchmarks/results/releases/0.6.2/source_integration.json) |

## Detailed Proof Records

Fresh installed acceptance uses the final core 0.6.2 wheel, SDK 0.6.0 and
reference extension 0.2.0. Eight end-to-end cases pass with no skips. Core,
SDK and extension imports are asserted to resolve under the isolated environment's
site-packages. The invocation omits provider/model overrides, exercising the
llama.cpp/Qwen3.8 defaults. The extracted external sdist is strictly validated.
Before-write and after-write injected process exits recover without repeating a
write. Expected refusal/denial is safety proof, not successful objective completion.
The exact command, artifact hashes, receipts and test outcomes are retained in
[acceptance.json](benchmarks/results/releases/0.6.2/acceptance.json).

Fresh installed surface execution goes beyond help/import checks: interactive
runtime startup receives `quit` and exits zero; a handled invalid runtime command
exits one; the packaged demo writes its evidence bundle; the copied source API
launcher serves a real HTTP 200 health request and is terminated and reaped.
The existing fresh-workspace reconciliation warning is explicitly classified
as `degraded` with result `success`.

The unchanged runtime implementation previously passed 10 live source integration
cases and the exact 1000-case JSON / 500-case tool promotion corpus. All 1500
native input token counts matched reported usage and native render checks passed.
The strict promotion decision is ready. Byte-backed template auditing, repeated
cache use, changed histories, cancellation/recovery, stop/sampling controls,
native-budget refusal and real bounded repair are separately evidenced in
[promotion readiness](benchmarks/results/releases/0.6.2/promotion_readiness.json),
[runtime readiness](benchmarks/results/releases/0.6.2/runtime_readiness.json) and
[repair readiness](benchmarks/results/releases/0.6.2/repair_readiness.json).
These corpus runs precede the version-only release preparation; they were not
rerun or relabeled as tests of a different model/server configuration.

## Artifact and Regression Verification

The final wheel and sdist are built from a clean staged source tree, avoiding
historical checkout build residue. All 840 packaged files match source bytes;
the wheel contains zero SDK namespace entries and installed `pip check` passes.
Hashes and source-evidence bindings are in
[artifacts.json](benchmarks/results/releases/0.6.2/artifacts.json).

The completed full regression result on the final runtime implementation is
**4609 passed, 74 skipped, 2 warnings**. Fresh release checks pass **43 tests**
covering release policy, authority docs, template audits, promotion gates and
real wheel/sdist package contents. No new runtime change follows the full suite.
Evidence: [regression log](benchmarks/results/releases/0.6.2/regression.log),
[release checks](benchmarks/results/releases/0.6.2/release_targeted.log).
Project hygiene, dependency direction and whitespace checks pass. Changed Python
code adds zero Ruff diagnostics relative to HEAD; repository-wide lint is not clean.

## Remaining Blockers or Drift

No blocker remains for the bounded llama.cpp release path. Architecture checklist
AC-01/02/03/05/07/08/09/10 passes for the touched behavior under the existing
transition rules. AC-04 and AC-06 remain partial at the existing runtime clock
helpers and adapter classification boundaries, including
`orket/adapters/llm/local_model_provider.py`; this change does not widen those
exceptions. The active
[architectural-truth plan](docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)
and its exception register remain the remediation authority. The release does
not claim repository-wide architecture conformance.

No hosted CI execution, PyPI publication or production soak is verified by this
report. Git branch/tag publication is verified separately after push. The
external README update is a separate documentation commit and does not replace
the original extension 0.2.0 release artifact. Its repository currently has no
configured remote; that does not block the core push.

Orket Core records checklist-backed acceptance for this bounded patch scope,
subject to exact commit/tag alignment and successful push. Routine live proof
sets `ORKET_DISABLE_SANDBOX=1` and creates no sandbox resources.

## Exact Files Touched

The complete commit inventory is [FILES_TOUCHED.md](docs/releases/0.6.2/FILES_TOUCHED.md).
