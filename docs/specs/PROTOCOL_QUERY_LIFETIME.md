# Protocol query ownership

Last updated: 2026-09-18
Status: Active
Owner: Orket Core

`ProtocolReplayService` owns protocol replay, comparison and parity queries.
CLI commands delegate to application command dispatch; HTTP routes retain their
workspace-scoped service. Query results are inspection evidence, never execution,
continuation, effect approval or completed-work authority.

## Inputs and path scope

Each operation captures its root selection, scalar options and requested run/session
ids before awaiting. Path resolution and file inspection run in retained workers.
HTTP file operands and resolved link targets must remain under the selected
workspace. Each requested or discovered run/session directory and its events log
must also remain under the selected runs root. Replay campaigns apply that tighter
runs-root check to receipt and artifact targets too. Invalid paths fail before
ledger comparison. This is application path validation, not hostile-process OS containment
or protection against a cooperating filesystem changing after validation.

The CLI's explicit event, artifact, campaign-root and SQLite options remain
operator-selected file operands; relative overrides use the captured invocation
directory. HTTP does not acquire that authority. Run ids remain identifiers within
the selected runs root rather than an alternative way to escape it.

## Lifetime

Cancellation retains admitted file workers and asynchronous query cleanup until
they settle, including repeated cancellation. Worker failure remains an error.
API shutdown therefore cannot report completed request teardown while its replay
worker still reads files. This adds no forced thread termination or shutdown
deadline. A stuck underlying filesystem can delay cancellation and teardown.

Parity queries compare separate observed projections. They do not provide a joint
transactional snapshot of SQLite and protocol files. Existing SQLite WAL admission
may create operational journal artifacts; query ownership is not a byte-for-byte
non-mutation guarantee for SQLite files. Two absent projections may have equal
parity with null digests; that is absence agreement, not evidence of a run.

## Replay evidence

Protocol state comparison requires a non-empty event sequence on both sides.
Absent/empty sequences produce `comparison_status=insufficient_evidence` and
`deterministic_match=false`, even when their reconstructed default digests agree.
Populated comparisons report `matched` or `mismatched`, with scope
`observed_protocol_state` and both event counts. This does not certify complete
execution, receipt authenticity, or a terminal run; stronger existing compatibility
and artifact-completeness options remain separate.

A campaign must preserve its comparator's result for the baseline itself.
Insufficient evidence counts as a mismatch for the campaign and strict CLI gate.
It can have zero content differences: lack of evidence is not a fabricated content
difference. Existing result fields and transport exit/error mappings are retained.
