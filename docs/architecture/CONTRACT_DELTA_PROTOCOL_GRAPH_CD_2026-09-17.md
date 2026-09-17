# Protocol run graph values and publication

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: graph cases pass in source/four installed cells and eight live llama.cpp cases pass; broader installed acceptance is false due to retained Linux resume failures.
- Affected contracts: protocol graph imports, file replay, terminal publication,
  retry repair and supported in-process value inputs.

## Delta
- Pure reconstruction is `orket/core/contracts/run_graph.py`; structural graph
  vocabulary/validation is `orket/core/contracts/run_graph_contract.py`.
  Explicit canonical JSON captures nested values before projection. Unsupported
  objects refuse instead of invoking arbitrary object-to-string conversions.
- Storage reads and writes belong to
  `orket/adapters/storage/run_graph_artifact.py`. File replay is asynchronous and
  retains its complete read/projection worker through caller interruption.
- Protocol finalization first appends its terminal ledger event, then derives the
  graph from observed events. A refused terminal event cannot publish a graph
  describing an event that never committed.
- Graph publication uses the shared same-parent temporary file, flush/fsync,
  replacement and read-back verification helper. Output is UTF-8 JSON with LF
  newlines. A content mismatch raises registered `E_FILE_WRITE_UNVERIFIED`.
- A graph write failure after terminal append leaves that terminal event durable
  and reports failure to the caller. It does not roll the ledger back. Retrying
  the same finalization derives and verifies the graph again, without duplicating
  the terminal event; this repairs missing or corrupted projections.
- Cancellation can leave a committed terminal event awaiting projection repair.
  An already admitted file worker remains owned until it settles. No completed
  publication is claimed solely because the worker was launched.

## Migration
1. Replace imports from both retired runtime graph modules with the core or storage
   module above. No compatibility shim is introduced.
2. Await `reconstruct_run_graph_from_events_log(...)`. Pure
   `reconstruct_run_graph(events, ...)` remains synchronous and has no file effects.
3. Call synchronous `write_run_graph_artifact(...)` only in an owned storage worker;
   protocol repository finalization supplies that worker and its local lock.
4. After a reported post-append projection failure or interruption, inspect the
   durable ledger and retry its same finalization to repair the derived artifact.
   Do not reinterpret the failure as proof that the terminal event was rolled back.

## Proof and limits
- Five pre-change real-file counterexamples are retained under `.tmp/c-run-graph/`.
  They cover premature publication, missing/corrupt retry, writer cancellation and
  absent read-back verification. Additional tests cover owned replay responsiveness
  within a declared 0.5-second loop bound, explicit input capture and invalid values.
- Retained pre-refactor JSON inputs preserve graph values and digests. An initial
  extraction omitted compatibility artifact `event_seq`; parity caught it, the
  field was restored and the mismatch remains retained.
- Existing `run_graph.json` schema/version and node/edge meaning stay unchanged.
  `run_evidence_graph` remains a separate projection family. Neither artifact
  becomes terminal execution authority.
- This is not an atomic ledger-plus-graph transaction, cross-process fencing,
  protection against arbitrary concurrent external editors, power-loss durability
  certification or a new path-containment guarantee. Existing root/session binding
  limits and broader C/D work remain open.
- The canonical remediation plan owns current source, installed and live proof.
  Prior host-clock instability and Linux approval/resume deadlines remain open.

## Versioning
- Candidate core `0.6.7`; SDK remains `0.7.0a1`.
- Internal import removal, async replay and post-append failure observations require
  migration. Work-hours commits and tags remain local; release and whole-lane
  acceptance are separate gates.
