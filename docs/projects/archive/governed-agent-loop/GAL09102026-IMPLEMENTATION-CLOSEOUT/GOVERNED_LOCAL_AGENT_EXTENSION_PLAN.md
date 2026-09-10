# Governed Local Agent Reference Extension Plan

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Last updated: 2026-09-09
Date: 2026-09-06
Status: Archived — accepted implementation closeout
Owner: Orket Core for reference contract; extension implementation remains externally packaged
Coordinating authority: `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
Durable contract: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`

Execution status: the public-SDK template, separate local external package,
deterministic fixture, live Ollama single/multi-model paths, structured repair,
and effect-proposal/resume integration are implemented. Hosting, publication,
and user acceptance remain Slice 7 work. Clean external source-distribution
retention, three-wheel installation, and strict installed host/SDK validation
are proven in `SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`.

## Objective

Current checkpoint: the actual external package at
`C:/Source/Orket-Extensions/GovernedLocalAgent` now compacts prior reports,
counts staged sources without duplication, and optionally uses host-admitted
objective memory. Its `scripts/release.py` validates version/tag alignment and
the extracted source distribution. Exact installed proof and release blockers
are consolidated in `SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md`; hosted repository
selection and publication remain separate release actions.

Build one external SDK-first reference extension that demonstrates a bounded
agent using multiple local-model roles while Orket retains authority for loop
progression, effects, budgets, recovery, and final truth.

The selected product shape is a fixed planner, actor, and critic team. It is
not an unrestricted swarm and it does not create an alternate runtime inside the
extension.

## Product outcome

An operator submits one objective and policy to Orket. For each admitted
iteration, Orket invokes the extension with an immutable context package. The
extension consults configured local-model profiles and returns a structured
iteration result. Orket then verifies observations, governs effects, records
truth, and decides whether another iteration may start.

## Packaging boundary

The extension must:

1. live in its own external repository using the canonical external-extension
   template;
2. use only the public `orket_extension_sdk` surface, installed from a pinned
   development wheel during integration and a released distribution at release;
3. declare every capability and standard-library import;
4. pass strict SDK import scanning and host validation;
5. publish through the existing source-distribution and tag flow.

The extension must not:

1. import private `orket.*` modules;
2. read Orket databases or control-plane artifacts directly;
3. read provider credentials or select raw endpoints;
4. execute filesystem, shell, network, VCS, or issue mutations directly;
5. run its own unbounded loop, scheduler, or daemon;
6. treat a model or critic recommendation as verified completion.

V1 admits reviewed, operator-trusted extension code. Python subprocesses and
import guards do not isolate hostile code from its OS account. Tests may prove
that this reference implementation uses the broker and emits no direct mutation;
they must not claim that arbitrary Python code cannot bypass it. Host-side scope
checks remain mandatory for every broker operation.

## Fixed first topology

1. Planner
   - receives the objective, authoritative observations, budget, and prior
     verified results;
   - proposes the next bounded intent;
   - uses a host-resolved reasoning profile.
2. Actor
   - converts the planner's advisory intent into content or effect proposals;
   - uses a host-resolved tool-capable or coding profile;
   - never executes the proposed effects.
3. Critic
   - evaluates the proposal against the objective, policy summary, and evidence;
   - returns advisory defects, uncertainty, and a continuation recommendation;
   - uses an independently configured review profile.

An operator may map several roles to the same physical model when local capacity
is constrained. Role identity and model identity must remain distinct in output
and telemetry.

## Iteration behavior

For each invocation the extension must:

1. validate the host-issued iteration request and supported contract version;
2. fail before model work if identity, budget, context, or checkpoint inputs are
   malformed;
3. call only the role profiles admitted for that iteration;
4. keep intermediate role outputs advisory and size-bounded;
5. derive effect proposals without executing them;
6. attach evidence refs to progress and completion recommendations;
7. return one canonical `AgentIterationResult`;
8. stop local work promptly when cancellation or budget exhaustion is observed.

Default reference limits, enforced within host-issued allocations:

1. one primary call per enabled role, with zero repair calls by default;
   an explicit bounded repair allocation may permit extra calls, all charged
   to the same role and run budgets;
2. one iteration executes sequentially;
3. no dynamic role creation;
4. no background child workload;
5. no capability or budget self-extension.

## Workstream 0 - External package scaffold

1. Use extension id `governed-local-agent`, package name
   `orket_governed_local_agent`, and external repository name
   `GovernedLocalAgent`.
2. Scaffold from `docs/templates/external_extension/`.
3. Declare the agent workload and only the capabilities admitted by the accepted
   SDK contract.
4. Establish canonical install, validate, build, verify, and tagged release
   scripts.
5. Add an extension-local design note describing the authority split with Orket.
6. Use an isolated external source directory and clean installed SDK environment
   for Slice 2 development proof. Creating a hosted repository or publishing a
   tag/distribution is a separate authorized release action, not a prerequisite
   for proving the external packaging boundary locally.

Acceptance gates:

1. SDK validation, import scan, host validation, and extension tests pass.
2. Source distribution preserves the manifest, source, tests, and scripts.
3. No internal Orket imports or undeclared standard-library imports exist.

## Workstream 1 - Deterministic fixture agent

1. Implement the iteration state machine against deterministic fake model
   capability providers owned by the host. The installed fixture must use real
   SDK proxies and the real child/broker path, not replace either with in-process
   fakes for the vertical-slice proof.
2. Cover one objective that completes without effects.
3. Cover budget exhaustion, malformed input, repeated state, no progress,
   cancellation, and critic rejection.
4. Prove canonical output is identical for equivalent explicit inputs.
5. Prove `completion_recommended` remains advisory in every extension result.
6. Use the coordinating plan's two-batch ticket-count JSON report, not a separate
   extension-only objective. Consume bounded objective, acceptance, source, and
   prior-result contents through the selected public context-delivery contract;
   bare host artifact references are not sufficient model input.

Acceptance gates:

1. Deterministic fixtures require no local inference server.
2. Every stop recommendation has a stable reason and evidence refs.
3. The extension cannot emit authoritative success or bypass the host result
   vocabulary.
4. The deterministic installed run crosses two admitted iterations and exercises
   the same verifier used by live runs. Extension-local role tests are unit or
   contract proof only; fake inference does not establish local-provider support.

## Workstream 2 - Single-model live baseline

1. Exercise the accepted single-agent sequential loop using one real local model
   profile.
2. Validate structured-output and truncation behavior for that named model and
   provider path.
3. Record actual provider/profile identity, token usage, latency, and finish
   reason.
4. Establish a bounded repair policy for malformed model output.
5. Fail closed when the selected local model cannot satisfy the required
   response contract.

Acceptance gates:

1. One real iteration completes through the external package and public SDK.
2. No direct effects occur.
3. Observed path and result are recorded as required by contributor policy.
4. Completion of this workstream requires a two-iteration run using the shared
   report fixture and verifier in the coordinating plan. The single invocation
   above is an intermediate integration check only.

## Workstream 3 - Fixed multi-model team

1. Add planner, actor, and critic profile requests.
2. Define bounded, typed internal handoff objects between roles.
3. Keep context per role minimal and derived from authoritative iteration input
   plus earlier advisory outputs from the same invocation.
4. Record each role's requested and actual model profile, usage, latency,
   truncation, and normalized result.
5. Support policy-approved profile substitution and model unavailability without
   silently changing role semantics.

Acceptance gates:

1. A live run uses at least two distinct local model identities.
2. Planner, actor, and critic outputs remain separately inspectable.
3. One role failure produces a truthful partial or failed iteration rather than
   fabricated team success.
4. Equivalent deterministic fixture inputs preserve canonical output.

## Workstream 4 - Governed effects and approval interruption

1. Add one low-risk read proposal and one bounded local mutation proposal.
2. Route both through the SDK effect-proposal contract.
3. Prove this reference implementation routes the mutation through the host;
   do not present an import scan as hostile-code containment proof.
4. Exercise host policy rejection, operator approval, operator denial, effect
   success, effect failure, and effect uncertainty.
5. Consume only host-verified effect receipts on the following iteration.
6. Stop or pause when the effect boundary is uncertain.

Acceptance gates:

1. No mutation occurs before host authorization.
2. Approval interruption survives process restart through Orket authority.
3. Denial is terminal or resumable only as resolved policy specifies.
4. Narration never describes a proposed effect as completed.

## Workstream 5 - Memory, handoff, and recovery behavior

1. Use objective-scoped memory for advisory working context.
2. Keep profile memory writes behind host policy and explicit provenance.
3. Prove host-built role contexts contain only admitted data. Roles sharing a
   Python process are context partitions, not security principals; the extension
   can see the data delivered to that process.
4. Emit typed handoff proposals rather than raw conversation-history transfer.
5. Reconstruct each invocation from the host request and durable refs after an
   extension-process crash.
6. Prove the extension does not self-resume merely because local state exists.

Acceptance gates:

1. Memory trust and scope survive round trip without widening.
2. Crash-before-result causes no proposed mutation or memory write to commit;
   already-consumed inference and host audit records remain recorded. Retrying
   requires a host decision and consumes fresh model budget.
3. Crash-after-effect-proposal does not duplicate an admitted effect.

## Workstream 6 - Operator experience and release proof

1. Document model-profile configuration, minimum hardware assumptions, provider
   preflight, policy limits, and failure diagnostics.
2. Provide deterministic example objectives and one live local-model example.
3. Ensure the Orket session inspector can distinguish each role, model call,
   proposal, effect receipt, budget change, and continuation decision.
4. Build and verify the authoritative source distribution.
5. Prove operator intake by extracting it and rerunning strict host validation.
6. Record exact core/SDK/extension artifacts and imported package locations in
   the clean external environment. Require the SDK plan's package-ownership and
   compatibility gates before relying on a separately installed development SDK.

Required test classification:

1. `unit`: role prompt construction and deterministic transforms.
2. `contract`: iteration, role output, effect proposal, handoff, and manifest
   validation.
3. `integration`: public SDK capability invocation and host effect routing.
4. `end-to-end`: installed external extension, real Orket host, and named local
   model profiles through terminal truth.

Routine proof must set `ORKET_DISABLE_SANDBOX=1`. Any explicit sandbox proof
must verify teardown in the same execution path.

## Completion criteria

This plan is complete only when:

1. the extension installs and validates without repository-private imports;
2. deterministic fixtures cover all required stop and interruption paths;
3. one live single-model run and one live fixed multi-model run complete through
   the public SDK;
4. one governed effect completes and one denied effect remains unapplied;
5. restart and cancellation behavior are proven;
6. Orket alone publishes authoritative continuation and final truth;
7. the user accepts the external author and operator experience.

## Follow-on candidates

1. Additional fixed role packs.
2. Dynamic delegation with parent-child budget allocation.
3. Background specialist workers.
4. Cross-machine agent workers.
5. Adaptive model-profile routing based on measured quality and capacity.

These are not part of the reference extension first slice.
