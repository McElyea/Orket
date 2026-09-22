# Provider inference HTTP input and construction ownership

Owner: Codex for Orket Core
Date: 2026-09-22
Status: Scoped implementation contract; acceptance remains in the canonical plan

At v0.6.91, the public factory and complete() path ignore supplied network policy in favor of
ambient proxy settings. Six real controlled TCP cases fail on source and the exact
installed v0.6.91 wheel; two ambient-default controls pass. These are protocol-valid
fixture responses and pinned fixture targets, not actual-model inference.

For intended patch 0.6.92, reuse the catalog network compiler/native TLS builder
and one acquired-resource cleanup owner. Bind an explicit application HTTP ownership
port to the inference adapter. Capture environment/directory before async dispatch,
refuse native construction on the event loop, and retain construction/cleanup through
interruption. Reuse existing runtime-result ownership for completed-but-unadopted
providers; do not duplicate its worker or cancellation loop.

Migrate async application callers and tests to owned composition while preserving
behavior assertions, case identities, deadlines, parser/profile/admission semantics
and backend-specific redirect/timeout policy. Capture Ollama outbound authentication
explicitly through public HTTPX auth, overriding the SDK's ambient default header.
No private SDK manipulation, environment mutation or unverified TLS is permitted.

Durable authority: `docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md` and the existing
catalog input contract. Native embeddings use the synchronous factory under native
ownership; async embeddings use async composition. Raw adapters supply the HTTP
ownership port. SDK native construction is also offloaded and drained by async
callers. Explicit constructor fixtures bind the supplied owner, including the
controlled ProductFlow provider; they do not claim real inference. Non-finite model budgets now refuse before effects.

Acceptance requires actual proxy/origin/TLS and credential observations, interrupted
construction/request/close, partial acquisition failures, responsive independent
work and installed artifact binding. Preserve all .91 catalog and earlier BT proof.
Failed acceptance blocks publication: revert code and authority together and retain
every observation. No actual-model/CAP acceptance, Linux clock repair, complete
D/E/CAP, release readiness or lane retirement follows from this scope.

The added native guard exposed a real SDK workload migration gap after the initial
source/native cohort passed: the async parent constructed an unused default model
provider on the event loop. A real default `model.generate` subprocess-path test
reproduced `E_PROVIDER_FACTORY_REQUIRES_ASYNC_OWNER`. Preserve early forbidden
host-bound capability validation through one shared configuration validator; remove
parent provider materialization. The native child retains newly constructed default
model providers immediately and closes them before publishing any result. Cleanup
failure preserves the prior workload result and capability report but cannot remain
successful. Borrowed configured providers retain caller ownership. The prior passing
matrix is retained as incomplete migration evidence, not final acceptance.

The later installed Python 3.12 matrix found one repeated-cancellation failure in
card prompt preparation. Two deterministic held-cleanup cases confirmed actual HTTP
closure with the provider's close result unadopted. Primary and ODR-auditor cleanup
now run through the existing owned-operation mechanism; the inner close finishes
before caller cancellation propagates. Keep the failed installed matrix and both
counterexamples. A fresh frozen source/installed matrix is required after this repair.
