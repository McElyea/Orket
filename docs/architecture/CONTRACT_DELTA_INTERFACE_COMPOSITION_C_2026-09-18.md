# Transport factories and runtime policy composition

Owner: Orket Core
Date: 2026-09-18
Status: implemented scoped checkpoint; full C/D/E/CAP acceptance remains open

## Summary and delta

`orket.runtime.policy.composition` currently imports API, CLI and webhook
transports. Its public factory exports through `orket.runtime` and the historical
`orket.runtime.composition` alias put application authority above interface
entrypoints. The current graph reports four forbidden source/target pairs from
this module within the remaining cross-layer authority cycle. This is structural
evidence; it does not establish that every static cycle executes at runtime.

Move the three transport factories to
`orket.interfaces.runtime_entrypoints`. Application retains `CompositionConfig`,
engine composition and module-profile capability authorization. Interface
factories ask application to authorize their capability before importing or
constructing their transport. No new dependency exception, reclassification,
dynamic forwarding or application-to-interface compatibility shim is admitted.

Keep API project-root forwarding, distinct API ownership, CLI invocation/result
semantics and webhook required-configuration behavior unchanged. Existing module
profile precedence and error payloads remain. This does not claim that synchronous
settings reads, global webhook ownership or unrelated application initialization
now satisfy D's full input/async requirements.

The admitted-startup CLI refusal also needs a diagnostic correction. The unchanged
installed 0.6.18 process exits 1 but prints an empty exception message because the
keyword-initialized dataclass exception has no `Exception.args` rendering. Its
explicit string form will include the existing error code and message; structured
`to_payload()` values and failure exit status remain unchanged. Original evidence
is retained at `.tmp/c-policy-composition/cli-error-before/`.

## Migration

1. Patch checkpoint: 0.6.19. Import `create_api_app`,
   `create_cli_runtime` and `create_webhook_app` from
   `orket.interfaces.runtime_entrypoints` instead of `orket.runtime`,
   `orket.runtime.policy.composition` or its historical flat alias.
2. `CompositionConfig` and `create_engine` remain application exports. The
   existing CLI command and `python server.py` entrypoint retain their behavior
   and migrate their internal factory imports in the same change.
3. Keep the factory's module-profile gate. Directly importing an underlying
   transport constructor is not an equivalent replacement for admitted startup.
   The existing low-level API constructor remains available to explicit embeddings.
4. Migrate tests and active authority docs; retain old release proof as historical
   evidence. Verify disabled/unknown profiles, real API lifetime and declared store selection, public
   CLI status and signed webhook admission without contacting an external Gitea.
5. Run changed-caller and lifecycle regressions plus fresh installed package proof.
   Refresh the graph and inspect the actual remaining cycle verdict. Broad
   platform/Quality/provider and full C/D/E/CAP acceptance remain open.

## Existing storage contract and retained adverse observations

The first persistence fixture omitted required card fields and correctly received
422. The completed fixture then incorrectly assumed that different project roots
select different databases. Both apps in unchanged installed 0.6.18 select the
invocation-level store and can read each other's cards. This follows
`docs/specs/RUNTIME_STORE_BINDING.md`; it is not a new factory regression.
Explicit distinct `ORKET_DURABLE_ROOT` values at construction select separate
stores and yield 404 for the other app's card. `storage-before/` retains both
real old-package flows with only the factory import adapted in the current probe.
The current regression tests prove both bindings, authenticated writes/readback
and actual owner teardown. Earlier failing fixtures and logs remain retained;
no storage resolver, schema or isolation promise was changed to obtain a pass.

## Rollback and recovery

If profile admission, configuration forwarding or transport parity regresses,
revert factories and callers together. No durable schema or automatic data repair
is proposed. Reverting restores the known application-to-interface dependencies;
it is not architectural conformance. Preserve all original and candidate evidence.
