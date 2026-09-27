# Complete runtime-construction input propagation across application routes

## Summary
- Change title: Propagate one selected `RuntimeConstructionInputs` object through
  canonical CLI, API, child-pipeline and legacy-extension construction routes.
- Owner: Orket Core, architectural-truth D.
- Date: 2026-09-25.
- Target: 0.6.106 development candidate.
- Affected contracts: `SETTINGS_INPUT_OWNERSHIP.md`,
  `RUNTIME_EXECUTION_RESULT_CONTRACT.md`, the runtime-factory and resource-cleanup
  deltas, and the organization-loop ownership delta.
- Status: implementation contract. Acceptance and publication remain governed by
  the canonical architectural-truth remediation plan.

## Prerequisite and authority

Complete asynchronous capture is already governed by
`CONTRACT_DELTA_RUNTIME_CAPTURE_OWNER_D_2026-09-25.md`. This delta does not add a
capture implementation, executor, settings collector or compatibility snapshot.
It governs what canonical routes do with the selected object after capture.

A supplied `RuntimeConstructionInputs` is authoritative as a complete object,
including an empty environment or empty settings/preferences objects. A route
that accepts complete inputs passes the same object by identity to downstream
runtime constructors. It does not copy it, reconstruct it from fields, recapture
ambient state, or combine it with a legacy invocation-root/environment selector.
Path-only consumers may use its selected invocation root without becoming a
second construction-input owner.

When a public route still permits no complete object, its documented default
capture remains available. Under the complete async-capture contract, default
cwd, environment and unbound settings-location selection occurs when the owned
capture worker begins. Callers that require an earlier selection instant supply
an already captured object.

## CLI startup and route propagation

The CLI retains one `runtime-startup-checks` worker. That worker completes
onboarding/startup first and then performs the complete native capture before it
returns. There is no intervening await, second worker, or caller-task ambient
read between startup completion and capture.

The CLI post-onboarding capture intentionally uses persisted-after-preferences
mode. It ignores stale caller-bound snapshots for this startup refresh, selects
cwd, environment and the settings-service location in the startup worker, reads
preferences before settings, and allows preference migration to remove legacy
settings keys before the final settings read. Root, environment and location are
fixed before a held persisted read; collected values are fixed before downstream
construction. This special startup order does not change ordinary complete
capture's independently bound settings/preferences behavior.

The caller task receives `(startup_status, construction_inputs)` and explicitly
binds the returned settings/preferences before status emission, argument
handling, or component construction. Worker-local context binding is not treated
as caller-task publication.

That exact object is then used as follows:

- the CLI extension-manager helper receives it and passes it through the complete
  manager branch;
- `OrchestrationEngine` receives it at construction;
- `OrganizationLoop.create` receives it explicitly and cannot recapture it;
- the interactive `OrketDriver.create` route receives it without an environment
  selector; and
- extension, protocol, marshaller and workspace-path routes derive their paths
  from its invocation root rather than rereading `Path.cwd()`.

The CLI has one local binding for the selected object and no later
`capture_async` admission. Private signature migrations are coordinated without
compatibility defaults: startup returns the tuple and extension workload
execution requires its explicit invocation root.

## Driver, API host and child-pipeline precedence

`OrketDriver.create` accepts either a complete object or its existing optional
environment selector. Supplying both refuses with
`E_DRIVER_CONSTRUCTION_INPUTS_ENVIRONMENT_AMBIGUOUS` before observing either
selector. A supplied object is reused by identity. With no object, the driver
uses the existing complete async-capture owner. `project_root` remains an allowed
path relative to the selected invocation root; it is not a competing ambient
input selector.

An API runtime host with app-owned complete inputs forwards that object to its
chat driver and omits the legacy environment argument. A directly constructed
host without complete inputs retains its legacy environment route. The host does
not synthesize an object from its stored environment.

Child-pipeline preparation has this strict precedence:

1. use `parent_pipeline.runtime_context.construction_inputs` when present;
2. otherwise use the `PipelineWiringService` construction-input default when
   present; and
3. otherwise raise `E_CHILD_PIPELINE_CONSTRUCTION_INPUTS_REQUIRED` before any
   ambient recapture or child construction effect.

Parent selection therefore overrides the wiring default. An absent parent does
not authorize fresh ambient capture, and the required-input error takes
precedence over observing cwd, environment, settings, or child resources.

## Legacy extension propagation and API composition

`ExtensionManager` accepts either a complete object or the legacy
`invocation_root`/`environment` selectors. A complete object must be a
`RuntimeConstructionInputs` instance and is exclusive with either legacy selector.
An invalid type raises `TypeError`; a complete object combined with
a legacy selector raises `E_EXT_CONSTRUCTION_INPUTS_AMBIGUOUS` before selector
observation. Explicit empty values remain authoritative.

The manager's `project_root` and `catalog_path` remain extension storage/catalog
choices relative to the selected invocation root. They are not alternate runtime
input selectors. If complete inputs are absent, the existing worker-owned legacy
branch selects cwd and environment when that worker operation begins. Selection
must not move before worker admission.

For the asynchronous manager helper this intentionally moves legacy default and
supplied-mapping observation from before its first await to worker execution.
Callers requiring the earlier instant supply complete captured inputs. Direct
native manager construction retains its synchronous observation point.

The manager retains the complete object by identity and passes it through
`WorkloadExecutor`, `execute_plan_actions`, `ExtensionEngineAdapter.open` and the
constructed `OrchestrationEngine`. Installation and workload preflight obtain
operation environments from that selected object. The adapter captures complete
inputs only when no object was supplied; it does not replace an explicit object.
The separately owned workload-policy observation remains separate and is not
silently folded into `RuntimeConstructionInputs`.

API runtime composition passes the exact object selected by
`ApiRuntimePreparation` into `ExtensionManager`, together with the explicit API
project root and without legacy invocation-root/environment selectors. The same
identity reaches the manager and executor. Existing API container, engine,
interaction, lifespan and shutdown owners remain unchanged. The separate
`ExtensionRuntimeService` environment contract is not redefined by this delta.

## Lifetime and error precedence

This propagation adds no process, thread, executor, runtime or cleanup owner.
Existing construction and close authorities remain responsible for their
resources:

- a completed driver/runtime that cannot be transferred after construction
  interruption is closed by its existing factory owner;
- after transfer, `open_async_runtime_owner` and `open_runtime_owner` delegate to
  the existing `close_runtime_owner` settlement policy;
- repeated caller cancellation cannot abandon an admitted close; and
- native construction or close failure remains visible and takes precedence over
  caller cancellation under the existing contracts.

If a context body fails and its required owner close also fails, the exact close
failure remains outward, the body failure remains its implicit context, and no
new explicit cause, wrapper, or synthetic success is introduced. Cleanup is
attempted once by the route owner. Engine/driver nesting continues to close the
inner interactive driver before the outer engine. This delta does not weaken the
resource-cleanup contract's attempt-all behavior for runtimes that own multiple
close-capable targets.

## Migration plan

1. Retain the already implemented central async-capture owner; do not replay or
   duplicate it.
2. Migrate driver/API-host/child signatures and callers together, then legacy
   manager/executor/action/adapter propagation, API extension composition, and
   CLI startup/helper/loop/runtime composition.
3. Remove no public default that the contracts retain. Add no fallback for the
   coordinated private signatures and no compatibility object reconstruction.
4. Verify exact object identity and selector refusals without rendering captured
   environment mappings. Retain existing explicit-empty, migration, worker-start,
   cancellation, timeout, failure and cleanup controls.
5. Require real CLI, organization-loop, driver/provider, legacy install/action,
   API lifespan and child-pipeline closing proof, plus source and installed
   acceptance. Structural route spies or signature failures are not runtime proof.

## Rollback plan

A copied object, ambient recapture, changed selection instant, ambiguous selector
admission, lost migration, or changed error/cleanup precedence blocks publication.
Repair forward through the same capture, factory and close owners. Do not restore
an event-loop read, add a second snapshot authority, weaken identity to value
equality, or hide completed native effects. Retain failed evidence and any
persisted migration effects for recovery.

## Versioning and limits

This is a patch correction with coordinated internal signature migrations and an
explicit default-selection timing contract inherited from complete async capture.
It changes no settings schema, extension catalog schema, runtime-result schema,
workspace default, process deadline, or resource order.

The contract does not claim an atomic snapshot across process globals/files,
provider or remote-service success, installed-package parity, Linux acceptance,
hostile-code containment, extension catalog representation normalization,
completion of wider D/E/CAP work, or whole-lane release readiness. Prepared
patches and tests remain proposals until integrated and executed.
