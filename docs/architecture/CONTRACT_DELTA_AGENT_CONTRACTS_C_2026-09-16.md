# Governed-agent shared contracts and manual wake ownership

## Summary
- Owner: Orket Core.
- Date: 2026-09-16.
- Contract authority: `docs/ARCHITECTURE.md` dependency and layer rules.

## Delta
- Governed-agent invocation/broker ports and wake, schedule and webhook records
  move from `orket.application.services` to `orket.core.contracts`, retaining the
  four module basenames. Core owns their vocabulary, record definitions,
  validation and abstract protocol signatures. Application and adapters import
  the same canonical definitions; the retired modules provide no forwarding shim.
- The concrete `ensure_governed_agent_authority` invocation remains application
  behavior, now in `orket.application.services.governed_agent_authority`. Its guard
  protocol and exception live in core. No persistence or authority invocation
  implementation moves into core with these declarations.
- Manual wake CLI operations now call `GovernedAgentWakeCommands`, which owns
  repository composition, ingress/control invocation and returned state views.
  The interface retains argument parsing and request-file decoding. It does not
  import storage implementations or core repository protocols for wake dispatch.
- The application factory uses the existing runtime-input service, with an
  injectable input owner. Manual receipt time retains its UTC microsecond `Z`
  encoding; persisted and public view schemas retain their previous fields.

## Migration Plan
1. Internal consumers import the four contracts from core. Callers of the concrete
   authority helper import it from application. Old-module pickle names are not
   supported; retained operational records use the unchanged JSON schemas.
2. Embeddings calling the internal wake CLI runner supply the application command
   service. The public `orket agent wake` arguments, exit codes, idempotency and
   conflict semantics remain unchanged.
3. Require record-definition parity, real repository/dispatcher/control/iteration
   regressions, actual native wake commands across process restarts and the
   affected installed Windows/Linux Python 3.11/3.12 envelope.

## Limits and Rollback Plan
- Frozen dataclass fields do not make nested mappings deeply immutable. This
  relocation does not complete D's immutable decision-context requirement.
- Ports declare behavior; they do not prove concrete adapter authorization,
  containment, side-effect classification or arbitrary implementation safety.
- Other governed-agent CLI commands still have dependency debt. The whole C/D,
  quality, capability and release gates remain open in the canonical plan.
- On a parity or installed-flow failure, stop acceptance and repair the canonical
  contracts/consumers; preserve failed evidence and do not add reverse imports.

## Versioning Decision
- Development-candidate internal import/runner migration; no release/version bump.
- No new wire protocol, database schema, provider policy or compatibility shim.
