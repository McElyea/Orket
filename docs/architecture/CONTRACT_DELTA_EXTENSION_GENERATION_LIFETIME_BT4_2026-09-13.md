# Generic extension model generation lifetime

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`.
- Scope: synchronous generation workers, explicit builtin overrides, request-owned
  and application-owned model HTTP clients. The whole BT-4 gate stays active.

## Delta
- Previously caller cancellation could settle before its worker finished; override
  selection temporarily changed global environment variables and clients were not
  closed. New calls retain workers and cleanup through repeated cancellation.
- Overrides pass provider selection explicitly. Request-created builtin clients
  close in their worker on the same bridge loop used for generation.
- The API owns and closes its default model provider after admitted requests.
  Injected providers stay embedding-owned and retain override authority.
- Worker/cleanup failure takes precedence over cancellation on this seam. A failed
  cleanup prevents a successful API close claim; ordinary successful generation
  still has the existing versioned response and nullable timing contract.

## Migration Plan
1. Use the matched development host and SDK artifacts. No SDK protocol method or
   response schema changes in this delta.
2. Direct embeddings stop admission and await their calls before service close.
   Embeddings that inject providers remain responsible for their resource close.
3. Retain controlled before/after worker, concurrency and cleanup counterexamples,
   real TCP API shutdown checks, installed matrix and separate live llama.cpp proof
   in the canonical remediation plan.

## Rollback Plan
1. Preserve retained evidence and package identities. Stop affected admission if
   an integration cannot honor the ownership contract.
2. Do not restore environment mutation, detach a running worker, or convert failed
   cleanup into a successful shutdown claim.

## Versioning Decision
- Core candidate behavior repair; SDK remains the matched unpublished 0.7.0a1.
- No new release, tag, provider fallback, force-stop guarantee or remote inference
  termination claim. A stuck worker may keep local cleanup pending.
