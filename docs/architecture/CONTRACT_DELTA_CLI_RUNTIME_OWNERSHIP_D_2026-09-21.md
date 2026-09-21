# Runtime CLI construction and inspection ownership

Status: Active contract delta
Last updated: 2026-09-21
Owner: Orket Core

The canonical `orket runtime` entrypoint performs environment bootstrap before
entering its event loop. After startup binds settings, the CLI captures runtime
construction inputs and resolves its workspace against the captured invocation
root. The application factory owns engine construction through interruption and
closes a returned engine that cannot be transferred to its cancelled caller.
As already specified by `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`, it
cannot recover resources that a constructor acquires internally but never returns.
Direct async embeddings must bootstrap environment before entering their loop;
the owned constructor does not load a second ambient `.env`.

Application inspection retains native path resolution, board and artifact replay
reads, and manifest output through cancellation, timeout and worker failure.
Relative paths bind their invocation root before worker admission. Native failure
remains visible even while cancellation is pending. Required engine cleanup still
gates caller return. Existing successful/unfinished/cancelled typed-result
semantics and exit codes remain authoritative. Artifact replay remains diagnostic
observation, not completion or replay-verdict authority. Partial printed manifest
output is not transactional and is not rolled back on interruption.

Argument declarations live in `orket/interfaces/cli_arguments.py`, grouped by
command family with the existing order, flags, defaults, help and error behavior.
The canonical CLI entrypoint continues to import and use that single definition;
no duplicate parser or compatibility forwarding implementation is introduced.

This is a bounded ownership change. Driver construction, stdin and provider
cleanup now follow `CONTRACT_DELTA_DRIVER_LIFETIME_D_2026-09-21.md`. API run
diagnostic/observation reads follow `CONTRACT_DELTA_API_RUN_OBSERVATION_D_2026-09-21.md`.
Sandbox log ownership, broader captured inspection inputs and the complete async
inventory remain open. No forced thread termination,
atomic filesystem snapshot, new model inference or universal response bound is
claimed. The remediation plan records measured source/installed acceptance and
the latest passive Linux clock disposition.
