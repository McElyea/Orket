# Gardener Report Harness

Last updated: 2026-10-10
Status: Active

`examples/gardener_harness/gardener_harness.py` adapts Gardener's command harness
to the public submission contract in `GOVERNED_AGENT_TASK_SUBMISSION.md`.
Configuration and installation are in the example README. This is a source
example requiring installed core/SDK and a normally installed trusted report
extension. There is one host verifier, `structured_report.v1`; the proposed
`agent_advisory_report_verification.v1` feature is not admitted.

## Authority and input boundary

1. Gardener supplies the task, target cwd, model and read-only mode spec. Only
   report mode with plan permissions and no write/command/merge authority is
   admitted. Write modes refuse before source or model work.
2. The adapter supplies the SDK submission and materialized inputs; Orket owns
   admission, identities, observed clocks, provider selection, invocation,
   verification and terminal publication. The canonical provider default is
   reused; no provider switch is permitted after failure.
3. The adapter reads committed Git objects, never follows repository content as
   native file paths, and disables replacement objects and lazy fetching. Native
   Git and its local metadata/configuration are trusted operator dependencies.
   Only observed text-normalization settings are retained from global/system
   Git configuration; filesystem monitors are disabled. This is not isolation
   against a concurrently hostile local administrator or executable.
4. Target and convention repositories must be clean before collection. Selected
   symlink/submodule entries, invalid text, missing Git evidence and exceeded
   bounds refuse. Every selected extra directory's tracked files are included.
   Target defaults include root documentation, manifests, and text in docs/,
   .github/ and .gitea/, plus prompt-named files. Explicit target paths replace
   that default selection. Blob IDs and commit IDs bind source content.
   Trees allow 10,000 entries; the full inventory is retained locally. Above 128
   entries the prompt lists selected files and up to 128 root names, with counts
   and a digest binding the full inventory. Unread content remains unknown.
5. The run directory is outside all source repositories. No source code is run.
   Provider credentials and other ambient settings retain existing host policy;
   repository prose cannot authorize tools or select another completion rule.

## Lifetime and result boundary

Commands reuse `CommandProcessSupervisor` and require successful lifetime
settlement and complete capture. Partial capture, timeout, unsupported native
ownership or unconfirmed cleanup cannot produce a successful envelope. The
wrapper reserves time within Gardener's deadline for settlement and response;
external hard termination is not a delivered cleanup receipt.

The wrapper requires a successful CLI exit, successful final truth and exactly
one retained result matching the final authoritative reference. It checks that
the advisory report matches the submitted references and section contract.
Afterward it re-observes source cleanliness, commit and inventory; changed source
refuses the outward result without rewriting an already durable Orket outcome.
No atomic lock against other writers or rollback of their changes is claimed.

Success means delivery of a structurally valid advisory report over the captured
commits. It does not certify semantic truth, complete file-content coverage,
executed tests or fixes. The footer states that ceiling. Report-mode extensions
remain trusted Python, not hostile-code containment. Unknown cost stays null.

Failed runs retain inputs and any SQLite effects; explicit inspect/replay is the
recovery surface. Re-execution is a new invocation, never an implicit retry.
Unavailable providers/models are device-blocking; validation failures remain
failures. Stdout is one Gardener JSON envelope. The wrapper writes inputs and
uses the existing durable store, without a parallel JSON result authority.

## Evidence and model budgets

`ORKET_GARDENER_TARGET_PATHS` is a JSON list of relative files/directories.
`ORKET_GARDENER_CONVENTIONS_SUBDIR` selects a relative directory within each
declared extra root; resolved escapes refuse. A compact rubric must be authored
as a complete scope, never fabricated by silently chopping convention files.
Selected binary files, symlinks and submodules still refuse.

File and total content defaults remain 16 KiB and 64 KiB, configurable up to
512 KiB. These are capture bounds, not promises of model context capacity.
Submission defaults are 8192 input / 2048 output tokens; explicit configuration
also remains subject to the host prompt profile and model limits. Governed
requests preserve all admitted messages and refuse incompatible budgets before
generation. Exact llama.cpp rendering and conservative other-provider admission
are specified in `GOVERNED_AGENT_TASK_SUBMISSION.md`. Raising a capture limit
alone cannot enlarge the model context. No summarization changes the supplied
evidence. The complete JSON document travels in consecutive user-message chunks
of at most 131072 characters. Gardener admits 1 MiB of aggregate child output,
including model-call requests; each wire frame retains its separate 1 MiB cap.
An individual materialized input over 262144 encoded bytes refuses before
dispatch with `E_GARDENER_INPUT_TOO_LARGE`. Reduce individual file capture or
split the source document explicitly. Total capture can reach 512 KiB across
multiple inputs. Capture, encoded-item, wire and token limits remain independent.

Native Windows supports this wrapper and Orket. Gardener 0.3.0–0.4.2's full CLI imports
POSIX `fcntl`; use WSL for `gardener align` until upstream supports Windows.
This is a platform workaround, not a native Windows Gardener acceptance claim.

Gardener requires `summary` (at least 40 trimmed characters, beginning with
`GARDENER_SUMMARY:` and nonempty text after the prefix) and `findings` (at least
80 trimmed characters). The prompt requests checks, evidence/unknown coverage
and suggested actions. These structural checks reject title-only delivery;
they do not detect every vague, padded or factually wrong report. The generic
summary-only report example remains supported under its original configuration.
`completion_satisfied`, `evidence_sufficient` and `no_residual_uncertainty` refer
only to delivery under this contract, never to factual certainty of findings.

Model calls reserve five seconds inside the report deadline for failed-receipt
delivery and terminal publication. A settled timeout or connection failure in
the admitted report-only path records a failed receipt with unknown token usage,
charges the reserved input/output limits and closes through the existing
continuation policy. The run is `failed_terminal`, the attempt is failed with an
end timestamp and provider failure code, and final truth is unsatisfied (usually
`blocked` because the budget is exhausted). No inference retry occurs. This does
not claim remote model termination. Interrupted children, publication failure
and general/effectful governed runs retain their recovery requirements.
Failed CLI-result envelopes and subsequent wrapper report/source-check refusals
include `session_id: orket:<run_id>` and the exact inspect command when the CLI
result contains a run identity. A source-change refusal preserves the original
captured-snapshot outcome in SQLite; it does not rewrite that outcome as failed.
Pre-admission failures have no run identity. Child protocol failures expose only extracted SDK error codes;
arbitrary child stderr remains private diagnostic data.

## Verification

Both Quality selections include `test_gardener_harness_example.py`: real Git,
native wrapper/CLI/SDK child, SQLite, controlled provider HTTP, Windows paths,
symlink refusal, missing/dirty/oversized sources, post-model source mutation,
invalid reports and unavailable-model behavior. Controlled HTTP is not model
proof. Actual Gardener dispatch and llama.cpp acceptance are recorded separately
with the exact source revision, measured receipts and settled owned server.
