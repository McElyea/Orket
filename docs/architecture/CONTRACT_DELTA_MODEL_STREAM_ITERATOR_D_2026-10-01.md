# Model-stream iterator and transport settlement

## Summary
- Owner: Orket Core
- Date: 2026-10-01
- Contracts: `MODEL_STREAM_LIFETIME.md`, `SHARED_IO_CANCELLATION.md`, existing interaction stream events and commit intents.

## Delta
- Previously, breaking on STOPPED/ERROR or failing the event sink could leave the async iterator unclosed; cancellation did not retain explicit iterator cleanup.
- The builtin now uses the existing native/async resource owner to close the admitted iterator before return or commit. One cancellation reaches the operation; repeated interruption retains close and watcher settlement.
- Cleanup failure refuses completion and remains outward with body failure in exception context. Timeout remains a request to interrupt followed by cleanup, not a forced deadline.
- Native construction, responses, nested SDK/line iterators and clients use the existing worker and HTTP resource owners. Partial acquisition is cleaned up; native construction and explicit close failure escape rather than allowing successful finalization. Non-stream/fallback requests now use owned async HTTP.
- The native dependency gate rejected an intermediate adapter-to-application import. Composition now injects the core HTTP lifetime port; no policy exception was added.
- No new cancellation supervisor, provider switch, commit schema or iterator interface is introduced. Optional close ports reuse the existing resource cleanup contract; no arbitrary-resource guarantee is inferred for iterators without such ports.

## Migration Plan
1. No compatibility window or alias is added. Existing provider iterators keep `start_turn`/`cancel` and receive explicit close when available. Raw real-provider constructors now require an application `http_client_owner`; internal embeddings construct `ModelStreamHttpService` using explicit captured inputs. Stub and builtin invocation signatures are unchanged.
2. Preserve captured inputs, target refusal, advisory event flags and result/commit mappings. Borrowed provider objects remain borrowed.
3. Opening: five failing real loopback HTTP iterator controls on `v0.6.118` source. Retain held close, repeated cancellation, cleanup failure and healthy/error controls, plus existing input/admission and public interaction tests. B02 also retains real streaming, non-streaming, zero-token fallback, partial-body and captured network/authentication controls.

## Rollback Plan
1. Failed settlement or event/commit parity blocks publication.
2. Correct the bounded ownership implementation while retaining regression controls; do not reintroduce early-return success.
3. Observed provider effects cannot be rolled back by closing the iterator. No durable-state migration or redispatch is authorized.

## Versioning Decision
- Patch checkpoint at ATG-02 closure; no capability admission.
- Internal constructor migration is required for raw real-provider callers; classify that boundary as breaking. Builtin/operator event and commit schemas are preserved. Embeddings with a failing close port now observe its failure before completion.
- Windows source opening is recorded in `.tmp/atg02-proof.json`; final closing and installed/provider acceptance remain separately recorded queue gates.
