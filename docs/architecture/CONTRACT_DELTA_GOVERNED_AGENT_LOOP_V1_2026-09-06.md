# Contract Delta: Governed Agent Loop V1

Status: Accepted activation baseline; Slice 0 implementation active
Refined by: `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_REVIEW_2026-09-06.md`

## Summary

- Change title: Add a host-governed continuous-agent workload and public
  extension contract
- Owner: Orket Core
- Date: 2026-09-06
- Affected contracts:
  - `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
  - `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
  - `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
  - `docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
  - `docs/specs/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md`
  - `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
  - `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_PACKAGE_SURFACE_V1.md`
  - `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`
  - `docs/requirements/sdk/VERSIONING.md`
  - `CURRENT_AUTHORITY.md`

## Delta

- Current behavior:
  - Orket can execute external extension workloads through one governed
    workload-authority seam, but it has no admitted agent-loop workload;
  - the public SDK exposes a generic workload context/result and a narrow
    single-provider `model.generate` capability;
  - controller workload v1 is sequential, depth-one, bounded fan-out and
    fail-fast, but it is not a continuous-agent loop;
  - existing approval continuation is limited to explicitly admitted kernel and
    governed turn-tool slices;
  - provider resolution can target local providers, but there is no host-owned
    per-role agent model-profile contract;
  - no application-owned durable wake supervisor advances agent iterations.
- Accepted behavior:
  - add the `governed-agent-loop` workload with contract version
    `governed_agent_loop.v1` through the existing canonical workload catalog;
  - represent one objective as one run, one execution generation as an attempt,
    and each admitted sequential iteration as a step;
  - invoke one external SDK workload once per admitted iteration;
  - allow fixed planner, actor, and critic model roles within one invocation,
    while keeping dynamic child agents and parallel fan-out outside V1;
  - resolve provider, endpoint, model, profile, credentials, health, and capacity
    in the host and expose only admitted profile capabilities to the extension;
  - make extension observations, effect requests, progress, handoffs, and
    completion values advisory inputs;
  - require an application-owned governor to publish every continuation,
    recovery, and terminal decision from durable inputs;
  - route all effects through existing capability, approval, reservation, lease,
    effect-journal, and reconciliation authority;
  - add canonical `pause_run` as the bounded operator command that withholds the
    next iteration and enters `operator_blocked`; resume continues to use
    `approve_continue` or `approve_degraded_continue`;
  - add an application-owned durable wake queue and supervisor only after the
    bounded vertical slice, effect, and recovery paths are proven;
  - preserve final truth exclusively in the existing `FinalTruthRecord` regime.
- Slice 0 implementation checkpoint:
  - the canonical nine-family Draft 2020-12 wire schema is packaged with the
    public SDK source and has no host-private copy;
  - manifest-v0 now has a typed agent declaration requiring
    `agent.iteration.v1`, `governed_agent_loop.v1`, and `agent_stdio_ipc.v1`;
  - the host catalog preserves those fields, while generic SDK execution refuses
    agent workloads with `E_AGENT_RUNTIME_NOT_ADMITTED` before artifact allocation;
  - `pause_run` now exists in the canonical `OperatorCommandClass` binding;
  - no agent governor, broker, iteration adapter, or runtime admission is claimed.
- Why this break is required now:
  - a continuously available multi-model agent needs durable host authority at
    every iteration boundary rather than an extension-owned loop;
  - the current SDK cannot carry the identity, budgets, profiles, effects,
    cancellation, evidence, or completion split required for that boundary;
  - stretching controller workload v1 or current generic workload success into
    agent authority would create ambiguous execution and completion truth.

## Migration Plan

1. Compatibility window:
   - `manifest_version: v0` remains the only admitted manifest family;
   - existing SDK workloads and controller workload v1 retain current behavior;
   - existing non-agent workload declarations remain valid;
   - agent workloads require both typed agent declarations and the
     `agent.iteration.v1` broker capability marker;
   - older strict hosts reject the unknown marker, while the required live
     handshake prevents a permissive legacy path from running the entrypoint as
     a generic workload.
2. Migration steps:
   - add canonical iteration and model-profile schemas;
   - add SDK bindings and feature negotiation without private core imports;
   - register the governed agent workload through the canonical catalog;
   - implement a deterministic vertical slice that crosses at least two
     separately authorized iterations;
   - add a single-model external reference extension;
   - integrate effects, approval interruption, recovery, and cancellation;
   - add the fixed multi-model role path;
   - add durable wake scheduling and the session inspector after bounded runtime
     proof is green;
   - update active specs, author docs, templates, runbook, and current authority
     in each behavior-changing slice.
3. Validation gates:
   - existing extension and controller contract suites remain green;
   - unsupported host/extension combinations fail closed;
   - one iteration cannot advance without a durable governor decision;
   - extension code has no private `orket.*` import or direct effect path;
   - cancellation and teardown leave no extension child process, task, or queue
     claim; provider capacity remains explicitly reserved when stop cannot be
     confirmed;
   - crash-boundary integration proof observes no duplicated effect;
   - Ollama-backed single-model and fixed multi-model end-to-end proofs record
     actual model identities and usage;
   - final success always links to an admitted non-advisory verifier basis.

## Rollback Plan

1. Rollback trigger:
   - agent execution bypasses the workload catalog, continuation governor,
     capability gate, effect journal, checkpoint/recovery authority, or final
     truth publication;
   - SDK compatibility regresses for existing external workloads;
   - supervisor shutdown or recovery leaks work or duplicates an effect;
   - local-provider resolution silently substitutes unsupported behavior.
2. Rollback steps:
   - disable admission of `governed_agent_loop.v1` at the canonical catalog and
     feature-negotiation boundary;
   - stop and drain agent wake claims without deleting durable records;
   - retain existing generic extension and controller workload behavior;
   - revert only the failing implementation slice and keep its evidence for
     diagnosis;
   - require a new accepted delta before re-admission if semantics must change.
3. Data/state recovery notes:
   - append-only runs, attempts, steps, effects, operator actions, checkpoints,
     and final truth must not be deleted during rollback;
   - uncertain effects require reconciliation before retry or migration;
   - queued work remains blocked until its contract version is admitted again
     or an operator closes it.

## Versioning Decision

- Version bump type: Documentation activation causes no package bump. The first
  public SDK release is an additive minor SDK release; core release
  classification is decided at implementation closeout under
  `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
- Effective version/date: Contract accepted 2026-09-06; runtime behavior becomes
  effective only after its gated implementation slices pass.
- Downstream impact: Existing extensions remain supported. Agent extensions must
  adopt the new public SDK contract and will fail closed on hosts that do not
  advertise `governed_agent_loop.v1`.
