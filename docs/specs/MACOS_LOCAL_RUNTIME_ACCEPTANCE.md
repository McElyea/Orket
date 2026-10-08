# Apple Silicon local runtime acceptance

Last updated: 2026-10-06
Status: Accepted requirements; implementation and native acceptance outstanding
Owner: Orket Core

## Scope

The first Mac milestone covers an Apple Silicon macOS local CLI/runtime workflow:
isolated candidate-package installation, project setup, provider diagnostics,
truthful hardware observations, governance and native execution. Supported OS and
Python versions must be named in the actual acceptance record. This document does
not grant current Mac compatibility. Intel Macs, desktop application packaging and
OrketUI expansion are outside this milestone.

The existing native process contract remains authoritative:
`docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`. macOS must preserve its
deadlines, capture bounds, cancellation ownership, descendant cleanup and explicit
uncertainty. A process-group signal, process-table snapshot or leader exit cannot
establish complete descendant cleanup. Unsupported execution must refuse before
dispatch. No weaker backend or hidden provider switch satisfies these requirements.

## Operator contract

1. Install built core and matching SDK packages in an isolated environment and
   invoke public commands outside the checkout. Contributor editable installation
   remains a separate path. Document upgrades, removal and retained project state.
2. Reuse application setup and provider authorities for project selection,
   configuration, model availability and a prepared example. llama.cpp remains the
   default. Diagnostics distinguish discovery, inference and execution readiness.
3. Hardware reporting distinguishes dedicated VRAM, unified system memory,
   observed accelerator availability, advisory estimates and unknown observations.
   Missing NVIDIA telemetry is not evidence that Apple GPU capability is absent.
   Neither total memory nor model-tier heuristics prove that a model fits or runs.
4. Shared Windows behavior and required quality gates remain intact. Mac support
   does not alter the historical Windows-only ATG-v1 acceptance boundary.

## Required native acceptance

### Implemented hardware reporting boundary

`orket/hardware.py` observes the native OS/architecture and physical memory through
the existing worker boundary. A Darwin arm64/aarch64 observation reports a unified
memory platform, nullable dedicated-VRAM fields and `gpu_observation=metal_unverified`.
`unified_memory_gb` is system physical memory, not a GPU allocation budget. No
Metal-device or inference probe has occurred. Other hosts retain their legacy
NVIDIA readings with explicit `nvidia_observed` or `unobserved` attribution.

The manifest and system-health projection preserve these distinctions. The legacy
model-tier helper returns `None` for unknown fit; discovery does not discard an
installed model on that basis or recommend a larger unknown-fit model. Existing
non-Mac heuristic decisions remain advisory. NVIDIA-specific optional tool tiers
are not newly enabled. Direct hardware observation on an event loop refuses before
native work; application callers use the existing owned worker.

This implemented reporting boundary has controlled platform and native Windows
test coverage. Native Mac observation, Rosetta behavior, Metal availability and
model fit remain unverified. MA cases below remain mandatory.

### Cases

Every case must run against identified candidate packages on Apple Silicon macOS.
Platform simulation, Windows proof and controlled provider fixtures remain separate.

| ID | Required behavior and observation |
| --- | --- |
| MA-01 | Fresh isolated installation; import origins and public CLI outside checkout; package hashes recorded. |
| MA-02 | Guided setup follows published instructions and persists the selected project/provider inputs. |
| MA-03 | Approval causes the expected file effect; denial prevents it; independently inspect files and verify ledger. |
| MA-04 | A bounded actual llama.cpp-backed Orket workflow produces its declared result/evidence. |
| MA-05 | The GPU case retains actual Metal backend evidence; CPU success cannot substitute. |
| MA-06 | Native commands exercise success, nonzero exit, timeout, cancellation and output limits. |
| MA-07 | Leader-exit and detached/resistant descendant cases independently prove cleanup and settled capture. |
| MA-08 | Restart retains state in project paths containing spaces and non-ASCII characters. |
| MA-09 | Missing providers, failed verification and uncertain cleanup cannot produce success. |

Each required case reports pass, failure or blocker; mandatory skips cannot yield
overall acceptance. Run the canonical pytest layers and unchanged quality gates
appropriate to the change. Routine proof sets `ORKET_DISABLE_SANDBOX=1`; explicit
sandbox acceptance must establish resource teardown in its execution path.

## Evidence and external access

### Implemented setup and diagnostic boundary

`orket setup` extends the existing SetupService, persisting the selected default
model in organization process rules and provider/GGUF inputs in the existing
project `.env`. Publication preserves unrelated dotenv content, uses native
ownership and verifies each write. Earlier effects can remain after failure.
The once-per-process bootstrap loader accepts an explicitly selected `.env` path;
process environment values retain precedence. Initialization still replaces its
organization document; reconfiguration is not a general merge operation.

`orket doctor --project <directory>` reloads the project's model and environment,
uses canonical provider preparation, observes hardware through its native worker,
and probes the existing command owner. `--inference` additionally verifies one
bounded arithmetic response through the actual provider adapter. Catalog
admission, inference, command ownership and Metal observation remain separate.
The diagnostic never claims Metal use. Setup's `--run-example` invokes the
existing mock-proposal quickstart. These do not replace the required prepared
provider-backed workflow or native MA cases.

`orket demo local-agent --project <directory>` provides that prepared workflow
through the existing governed-agent submission, provider, native child and
verification authorities. Shared ticket-example builders own the staged inputs
for this command and its acceptance tests. The command diagnoses the selected
project, reserves a fresh contained output directory, materializes the packaged
agent template and publishes verified inputs through owned native workers.
Interruption retains admitted publication until settlement; earlier files may
remain. An existing destination refuses instead of replacing retained state.
The final `report.json` is a verified projection, not another completion owner.
Fresh `agent inspect` and `agent replay` invocations read the retained SQLite
state. Controlled HTTP tests establish local integration behavior only; MA-04
still requires actual llama.cpp on the identified Mac candidate.

Input validation refuses credentials/query parameters in endpoint URLs and
environment-expansion/control characters in managed values. No secret is added
to setup output or persisted into an endpoint. Existing API-key environment
configuration remains owned by the provider adapter.

The initial packaging producer is `scripts/ci/verify_candidate_install.py`.
Its stable `.tmp/macos-support/package-install.json` result and
`package-inputs.json` inventory retain diff ledgers. Fresh Git-visible sources,
separate wheels, isolated external installation and installed-byte comparisons
precede public command and deterministic quickstart proof. The installed ledger
verifier must reject a tampered copy. All commands use the existing native owner;
unsupported macOS ownership remains a dispatch blocker, not an exemption.
The missing-provider control holds a non-listening loopback port and uses the
diagnostic's valid default timeout. Its shared producer/receipt admission check
requires the selected project, provider, model and endpoint, the observed
connection-failure diagnostic, provider resource closure and successful native
command settlement. Configuration errors, catalog errors, authentication failures
or unsupported native execution cannot satisfy that control. Earlier receipts
without this evidence must be regenerated; a nonzero exit alone is insufficient.
The guide is `docs/guides/MACOS_LOCAL_INSTALL.md`; the manual Gitea packaging
workflow is `.gitea/workflows/macos-candidate-install.yml`. It runs packaging,
the process component below and the combined actual-provider producer. Each
component alone cannot close full acceptance. Fresh-process quickstart ledger
reads do not establish provider/workflow restart behavior.

The process component producer is `scripts/ci/verify_installed_process_acceptance.py`.
It requires a passing candidate-install receipt whose Git-visible package inputs
still match, installs the same wheel's dev extra, verifies installed origins/bytes,
and runs copied native verification, output-bound and outward-uncertainty tests.
The copied tests and helpers retain their source bytes. Each of the 27 required
items must run successfully; missing, duplicate, skipped and failed items refuse.
Its `.tmp/macos-support/process-acceptance.json` report covers MA-06/07 and the
process-failure component of MA-09, not all MA cases. Model output in the outward
uncertainty fixture is controlled; command execution, interrupted acknowledgement,
API reentry and retained SQLite state are real. `--windows-control` is explicitly
non-Mac proof. Current Mac backend admission remains blocked; backend declarations
must be updated with the verified MAC-02 implementation, not relaxed by the harness.

The combined producer is `scripts/ci/verify_macos_acceptance.py`, with stable
`.tmp/macos-support/native-acceptance.json` evidence. It admits matching package
and process receipts, rechecks installed bytes and unchanged dependencies, and
repeats quickstart effects/refusals in that environment. It then exercises actual
interactive setup, the prepared provider workflow, fresh inspection/replay and
saved project diagnostics. The bounded owned server uses the identified GGUF and
installed prompt template. Successful workflow calls to that server plus positive
Metal device/model allocation and layer offload are required for MA-05. Settled
cleanup, complete capture, port closure and unchanged authored inputs are required
before overall success. Every required MA case must have passing evidence.
`--windows-control` may return CONTROL_PASS with MA-05 blocked and overall Mac
completion false. It cannot substitute for native acceptance. The operator
procedure and authorization boundary are in `docs/guides/MACOS_ACCEPTANCE_RUNBOOK.md`.

Retain source revision and dirty-input identity, candidate hashes, OS/architecture/
Python versions, provider/model/backend identity, commands, exit codes, logs and
artifacts. Rerunnable JSON producers use the shared diff ledger and stable output
paths. Source changes invalidate affected proof. No benchmark publication is
authorized by this milestone.

Automation belongs in `.gitea/workflows/`, with jobs on a native macOS runner.
Workflow syntax and runner labels do not prove a runner is available or a job ran.
Remote provisioning requires a reviewable runbook and explicit authorization for
spend, accounts and source transfer. Until access exists, continue independent
work and preserve the exact resumable checkpoint. Native acceptance remains open.

## Completion

The implementation, updated authorities, required checks and MA-01 through MA-09
must all have adequate evidence before this milestone is complete. A documented
technical blocker is not completion. Changes to scope or acceptance need an
explicit user decision. The canonical execution queue lives in
`docs/projects/macos-support/MACOS_SUPPORT_IMPLEMENTATION_PLAN.md`.
