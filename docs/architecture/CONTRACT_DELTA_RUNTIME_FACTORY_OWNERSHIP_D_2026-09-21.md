# Public runtime factory ownership

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version/date: 0.6.59 candidate, 2026-09-21.
- Contract: `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`.

## Delta
The public orchestration helper and collection-member supervisor currently call
synchronous runtime constructors on the event loop. Four retained real-runtime,
native-file and SQLite cases block for 0.802–0.815 seconds against the predeclared
0.5-second response bound. A worker must be owned through interruption and any
returned runtime must be closed before its interrupted caller is released.

Share the runtime factory owner and existing close owner. Capture public helper
construction inputs and prepare collection constructor arguments before worker
admission. Keep worker errors visible and close a completed but unadopted runtime.
Keep required cleanup through repeated cancellation. Do not infer success from
normal return or replace typed collection outcomes with synthetic final truth.

## Migration and rollback
Existing public helper calls and result contracts remain; callers may supply
explicit `RuntimeConstructionInputs`. Async collection honors bound
settings/preferences independently and reads
unbound values through the existing settings service at captured locations.
Synchronous bridge refusal and preference migration rules remain unchanged. Internal
collection wiring changes from immediate `create_sub_pipeline` to a prepared
constructor callable, with its in-repository callers migrated together. No
compatibility alias or second constructor implementation is retained.
Sandbox, webhook and orchestrator wiring receive the runtime's explicit
construction snapshot; custom wiring ports must accept that optional keyword.
It overrides the service default for that invocation. This closes the observed
legacy-parent gap where a captured child still created its webhook store under
a later working directory through an inherited, unconfigured wiring service.

Partial resource acquisition inside a constructor that fails before returning
remains the constructor's responsibility. Direct engine/pipeline/runtime-context
construction and the ConfigLoader synchronous bridge now follow
`CONTRACT_DELTA_CONFIG_SYNC_BRIDGE_D_2026-09-21.md`; other constructor and caller
reachability remains open. Rollback restores
the event-loop blocking defect and must disclose it; histories are unchanged.

## Versioning and verification
Compatible public patch with internal factory migration. Require real runtime,
native-file, SQLite responsiveness, cancellation/timeout, cleanup-failure and
terminal-result regressions in source and installed artifacts. Keep the 0.5-second
response bound, worker deadlines and retained BT evidence. Linux clock acceptance
and whole-plan readiness remain separate gates.
