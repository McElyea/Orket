# Synchronous configuration bridge and owned runtime construction

Status: active bounded D contract delta; whole-lane acceptance remains open.

`ConfigLoader` synchronous load/list methods permit pre-loop and worker callers.
On an event-loop thread they close the newly created, unstarted coroutine and
raise `E_CONFIG_LOADER_REQUIRES_ASYNC_METHOD` before executing it. They no longer
block that loop waiting for a separate executor's `asyncio.run`. Async callers
use the corresponding async methods. Configuration parsing, fallback order,
identity materialization and pre-loop results retain their existing authorities.

`OrchestrationEngine`, `ExecutionPipeline` and `OrketRuntimeContext.from_env`
refuse direct event-loop construction before bootstrap/native effects with
`E_RUNTIME_CONSTRUCTION_REQUIRES_ASYNC_OWNER`. Pre-loop and worker construction
remain available; those callers own required cleanup. Async engine and pipeline
embeddings use `async with OrchestrationEngine.open(...)` or
`async with ExecutionPipeline.open(...)`. Their named workspace argument and
remaining constructor options are retained. Direct runtime-context builders can
use the existing `open_runtime_owner` with an explicit construction callable.

The shared configured factory captures workspace/config path values and bootstrap
inputs before construction. Relative workspace/config/database paths bind to the
captured invocation root. An explicit `RuntimeConstructionInputs` remains usable.
Injected repositories/services retain their identities; this is not a deep copy
of capability objects or an immutable snapshot of every configuration file.
Organization and other assets are still read by the existing worker-owned loaders.

The shared owner retains construction and required close through repeated caller
cancellation and timeout. An owner returned after interrupted construction closes
without entering the caller's body. Native construction, body and cleanup failures
remain visible; a successful body cannot make failed cleanup successful. Resources
discarded inside a constructor that fails before returning remain that
constructor's responsibility. No forced Python thread termination is promised.

Concrete async script and test callers now own these contexts. The witness-bundle
command owns its existing product-flow builder and closes before bundle publication.
That script retains its existing environment preparation; this does not establish
immutable inputs for all standalone product-flow helpers. Existing runtime action
bodies, result projection and accepted BT completion/effect authorities are retained.

This is a required migration for async library callers. `ConfigLoader` construction
itself, Agent root resolution, other synchronous helper lifetimes, broader captured
inputs and complete async reachability remain separate D work. Standalone CLI/CI
exemptions retain their contributor meaning. Existing script lint findings are
reported explicitly rather than suppressed or represented as a clean lint run.
Linux clock disposition, whole-suite coverage, E1/E2 and CAP remain open.

Measured proof and limits belong to the canonical remediation plan and
`.tmp/d-config-sync-bridge/`. Rollback must restore constructors and their callers
together and disclose the event-loop blocking defect. No durable record migration,
authority replacement or lane retirement is included.
