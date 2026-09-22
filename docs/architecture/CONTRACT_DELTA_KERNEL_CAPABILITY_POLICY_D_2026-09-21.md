# Kernel capability policy capture and distribution

## Summary
- Change title: Package and capture explicit immutable legacy capability policy
- Owner: Orket Core, architectural-truth D
- Date: 2026-09-21
- Affected contracts: kernel_api/v1 policy lookup, default provenance and direct native invocation
- Status: implementation contract; scoped acceptance governed by the canonical plan
- Durable authority: `docs/specs/KERNEL_CAPABILITY_POLICY_INPUTS.md`

## Delta
- Before: validator reads a relative policy file into a mutable process-wide cache.
  Foreign working directories lose or replace the default. Missing/malformed
  files silently become an empty policy, and reads can block an event loop.
- After: a single package-owned default and read-only adapter supply a validated
  immutable observation per evaluation. Requests detach before reads. Explicit
  typed inputs permit deterministic policy evaluation without filesystem access.
  Native failures propagate and precede current-turn staging effects.
- The default logical source becomes `policy://orket/kernel/v1/default`; policy
  version and permission contents remain unchanged. Evidence and turn digests
  containing default source metadata consequently change. Existing context
  overrides and trusted/advisory semantics remain; no new broker authority.

## Migration
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Replace references to the removed model-tree artifact with the packaged asset
  location authority. Update expected default source metadata and dependent digests.
- Repair malformed policy files instead of relying on the empty-policy fallback.
- Move native reads and execute-turn calls off running event loops using existing
  owned workers/lifetimes. Typed resolve/authorize calls are pure; bind typed
  inputs into a partial operation before passing through JSON-only `invoke_kernel`.

## Verification and limits
The plan records exact frozen source/installed cases, actual read/staging/ASGI
effects, retained v0.6.77 counterexamples, package resource parity and fixed
interruption/responsiveness bounds. Mock-free policy decisions and actual file
effects are exercised with controlled scheduling at the adapter boundary.
ASGI transport is in-process; no deployed server, inference or outward connector
acceptance is claimed. Complete D inventory, Linux timing, E/CAP and user
acceptance remain open. No lane retirement or release readiness is implied.
