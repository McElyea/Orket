# Contract Delta: Governed Agent Loop Slices 3-5

Status: Accepted bounded implementation; CLI and application-service paths only

## Summary

- Change title: Add live Ollama roles and issue-scoped governed agent effects.
- Owner: Orket Core
- Date: 2026-09-07
- Affected contracts: `docs/specs/GOVERNED_AGENT_LOOP_V1.md` and
  `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`.
- Authorization: the user requested implementation of the accepted plan and
  resolution of its outstanding design questions in the same work.

## Delta

- The dedicated CLI agent path may now select exact installed Ollama model
  identities with `--ollama-model` and optional fixed planner, actor, and critic
  overrides. The host resolves each target with auto-selection and auto-load
  disabled, owns the client, and records requested/resolved target identity,
  provider version, measured usage, latency, finish reason, and truncation.
- Provider errors and invalid or schema-nonconforming JSON become failed durable
  model-call receipts with normalized reasons. A host-issued repair allocation
  permits at most one extension-requested repair call; the call and measured
  usage remain charged.
- `read_file` and `write_file` are public manifest vocabulary only as host-bound
  effect-proposal capabilities. Child configuration cannot instantiate either
  capability, and the extension cannot invoke an effect executor.
- One run records exactly one admitted issue namespace. An agent effect proposal
  must match the issued run, attempt, step, iteration, capability, namespace,
  target, full arguments, arguments digest, and idempotency identity.
- `read_file` is observe-only and publishes a host observation receipt plus an
  effect-journal entry. `write_file` creates a stable existing pending-gate
  approval and reservation hold after a resume-forbidden pre-effect checkpoint;
  it cannot mutate before operator approval.
- Approval publishes the existing operator-action and reservation resolution,
  executes through the existing `ToolGate` and `FileSystemTools` boundary,
  re-observes the target, appends one effect-journal entry, and accepts a
  resume-same-attempt post-effect checkpoint. Resume still requires an explicit
  host operator action and a complete set of matching observed or reconciled
  effect receipts.
- Denial applies no effect, rejects the pre-effect checkpoint, publishes
  operator-terminal-stop final truth, and closes the run as failed-terminal.
- A restart after a write but before effect publication observes the intended
  target first. Matching content is recorded as reconciled without redispatch;
  a failed or contradictory observation records uncertainty and blocks resume.
- Fixed role handoffs contain only the typed bounded report payload required by
  the next role. Live single-model and two-model paths use the same host verifier;
  no model or extension completion recommendation publishes final truth.

## Exact Narrowing

1. The only agent effect namespace admitted here is the run's exact
   `issue:<issue_id>` namespace.
2. The only effect capabilities admitted here are observe-only `read_file` and
   approval-required `write_file` through the existing issue-scoped path.
3. The continuation reason `effect_approval_required` is distinct from
   `unresolved_effect_boundary`: the former pauses for an operator, while the
   latter enters recovery and requires reconciliation.
4. Checkpoint presence, approval status, queue lease expiry, or extension output
   alone never grants continuation.

## Explicit Non-Admission

This delta does not admit:

1. agent-controlled provider endpoints, model substitution, credentials, model
   loading, or local-capacity oversubscription;
2. general filesystem authority, shell/network/VCS effects, non-issue
   namespaces, or replacement-attempt continuation;
3. a governed-agent HTTP API, background task, durable wake queue, scheduler,
   webhook ingress, or continuous supervisor;
4. hostile-extension containment, package publication, or release compatibility
   beyond the recorded development artifacts.

## Migration and Compatibility

1. Existing generic/controller workloads and existing local prompting behavior
   remain on their prior paths.
2. Agent extensions that declare `read_file` or `write_file` require the updated
   SDK vocabulary and a host advertising both governed-agent features.
3. The CLI deterministic fixture remains available and mutually exclusive with
   live Ollama selection.
4. Existing durable Slice 1-2 records remain decodable; the added run namespace
   column is optional for non-agent runs and required by new agent effect work.

## Rollback

1. Remove live provider selection and stop advertising effect-capable agent
   manifests while retaining strict agent-path refusal elsewhere.
2. Preserve model receipts, approval rows, checkpoints, effect journals,
   operator actions, and final-truth records for inspection.
3. Never delete or reinterpret an observed or uncertain effect during rollback.
4. Keep the SDK schema version readable for retained records; publish a new
   version for any incompatible wire change.
