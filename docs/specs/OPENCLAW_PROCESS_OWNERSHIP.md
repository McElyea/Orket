# OpenClaw interactive process ownership

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

The JSONL adapter receives an application-owned command runner. Its command,
directory, environment and JSON-serialized requests are captured before dispatch.
One request is sent only after the preceding JSON-object response is accepted.
An invalid response stops further request admission. A failed exchange preserves
the accepted response prefix and identifies the first incomplete request.
JSON nesting beyond the decoder's capacity is refused as invalid protocol input
or response; it cannot escape as an unobserved native reader failure.

Interactive exchange belongs to the existing package-owned OS supervisor and its
Windows job/Linux subreaper backends. Do not add a competing tree owner or a
direct-child cleanup fallback. Leader exit, I/O failure, timeout, cancellation and
repeated cancellation must settle admitted descendants before releasing ownership.
Unconfirmed cleanup or incomplete capture cannot produce normal success output.
Cancellation carries the existing application's observed lifetime record.

Each request write and response wait has the configured finite I/O deadline;
stdin close and command exit are bounded too. The existing one-second minimum is
retained. The supervisor concurrently drains stdout and stderr and retains its
existing 4 MiB bound per output stream. JSONL responses retain the existing 64 KiB line
bound. Overall transport duration is bounded from request count and these deadlines;
deadline expiry is failure, never empty success. No deadline or output-bound override
may be introduced merely to make an acceptance probe pass.

Ordinary protocol/command failure returns the accepted partial response prefix.
Success requires every requested response, a clean command exit, complete capture
and confirmed cleanup. Process cleanup does not undo accepted external effects.
This is trusted-command lifecycle ownership, not hostile-code containment or actual
OpenClaw/model acceptance. Existing nervous-system fixtures remain fixtures.

Acceptance requires actual sequential exchanges, partial failure, bounded writes,
stderr pressure, output/line limits, cancellation/timeout, leader-exit descendants,
captured inputs, independent process/effect observers and installed artifact proof.
During a held exchange, unrelated SQLite work must remain below 0.5 seconds. Existing
command ownership, provider, Worker and BT behavior must remain verified. Full D,
Linux clock repair, E/CAP and lane retirement are separate acceptance obligations.
