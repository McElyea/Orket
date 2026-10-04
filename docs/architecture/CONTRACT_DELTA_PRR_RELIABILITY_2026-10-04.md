# PRR-v1 installed transport and grounding repair

## Summary
- Owner: Orket Core
- Date: 2026-10-04
- Affected contracts: `API_RUNTIME_LIFECYCLE.md` and
  `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`.

## Delta
- Fresh 0.7.1 wheels omit a WebSocket implementation. Native Uvicorn logs the
  missing transport and returns 404 to the public interaction upgrade. Core now
  declares the `websockets` dependency used by those existing routes.
- After transport installation, actual inference and cancellation exposed an idle
  WebSocket disconnect hang during graceful server shutdown. The interaction route
  now owns concurrent event forwarding and disconnect observation in one task
  group; either exit settles both tasks before existing subscription cleanup.
  This grants no cancellation authority over the separate workload.
- Residue extraction used to delete whitespace and concatenate text around
  removed JSON. `Maybe this...` escaped the existing whole-word grounding rule.
  Extraction now preserves whitespace and substitutes a separator for excluded
  JSON objects/object arrays. The marker vocabulary and JSON/tool-only exclusions
  retain their existing authority; no second parser or broader policy is added.
- These changes repair demonstrated behavior. The missing caller-owned board
  warning remains truthful under `RUNTIME_PROJECT_ROOTS.md`.

## Migration Plan
1. No compatibility shim or new protocol; install the matched core/SDK wheels.
2. Existing strict-grounding callers must comply with the rule already selected.
   Previously accepted speculative prose may now cause the existing corrective
   retry and refusal before any tool dispatch.
3. Gates: retained pre-fix parser and native installed upgrade failures; repaired
   parser-to-validator and turn execution controls; installed Windows 3.11/3.12
   actual llama.cpp completion/cancellation and local cleanup; release checks.

## Rollback Plan
1. A demonstrated regression blocks publication or requires a new patch.
2. Retain immutable published artifacts; use the previous matched pair when
   operationally necessary, acknowledging its recorded transport/grounding defects.
3. Existing durable commits are preserved. No schema migration or transcript
   persistence is introduced.

## Versioning Decision
- Patch: core 0.7.2 and packaging-only SDK 0.7.2.
- Public SDK behavior is unchanged. Windows-only proof remains bounded by the
  PRR plan; native local cleanup does not establish remote inference termination.
