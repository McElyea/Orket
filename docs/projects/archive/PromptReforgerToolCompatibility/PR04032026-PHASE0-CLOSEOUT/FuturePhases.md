## 21. Future Phases

The phases below are proposed future expansions of the current Phase 0 lane.

Phase 0 remains the bounded proof slice for Prompt Reforger as a generic Orket service surface. Later phases must preserve the same authority split:

- Prompt Reforger remains the generic Orket service surface,
- external consumers remain responsible for bridge ownership, eval ownership, orchestration, and matrix truth,
- Orket does not become consumer-specific.

### Phase 1 - Generic service contract hardening

#### Goal

Turn Prompt Reforger from a proven bounded slice into a stable generic service contract.

#### Focus

Phase 1 should harden and freeze:

- request and result envelopes,
- run identity and status surfaces,
- compatibility-bundle format for qualifying runs,
- canonical error and attribution mapping,
- SDK parity with the generic service surface,
- the verdict-source rule for external consumers.

#### Required clarification

Phase 1 must explicitly define the shared result vocabulary rule:

- Prompt Reforger owns service-result authority,
- external consumers may reuse the same class vocabulary,
- external consumers must record whether a verdict is:
  - `service_adopted`
  - `harness_derived`

Shared class labels do not imply shared authority.

#### Exit criteria

Phase 1 is complete only when all of the following are true:

1. one stable generic service contract exists;
2. request/result envelopes are frozen enough for external consumption;
3. run identity and run-status surfaces are stable;
4. compatibility-bundle format is stable for qualifying runs;
5. the service-result vs harness-verdict mapping rule is explicit;
6. SDK parity is implemented or explicitly deferred.

### Phase 2 - External consumer integration pattern

#### Goal

Prove that an external BFF/consumer can use Prompt Reforger repeatedly without pushing app-specific orchestration back into Orket.

#### Focus

Phase 2 should harden:

- external BFF invocation flow,
- bridge and eval ownership on the consumer side,
- consumer request composition rules,
- service result consumption rules,
- polling, resume, retry, and cancellation behavior across the boundary,
- the boundary between service truth and consumer truth.

#### Expected outputs

Phase 2 should produce:

- one repeatable external-consumer reference integration path,
- one documented BFF/service interaction pattern,
- one explicit verdict-source mapping path,
- one external proof record showing service use without consumer-specific Orket behavior.

#### Exit criteria

Phase 2 is complete only when all of the following are true:

1. at least one external consumer can invoke Prompt Reforger through the generic surface repeatedly;
2. the consumer owns orchestration, bridge, and matrix truth;
3. Orket remains extension agnostic;
4. the service-result vs consumer-verdict boundary is explicit and testable.

### Phase 3 - Production hardening

#### Goal

Make Prompt Reforger safe to operate as a real service rather than only as a future-lane proof surface.

#### Focus

Phase 3 should harden:

- auth and authorization,
- idempotent run behavior,
- cancellation and retry semantics,
- durable run records,
- observability and debugging surfaces,
- service versioning and compatibility promises,
- bundle requalification and drift handling,
- operational failure and support surfaces.

#### Exit criteria

Phase 3 is complete only when all of the following are true:

1. the service can be operated without ad hoc manual interpretation;
2. durable run and bundle surfaces exist;
3. run cancellation and retry behavior are stable;
4. drift and requalification rules are explicit and testable;
5. service behavior can be debugged and supported through stable observability surfaces.

### Phase 4 - Multi-consumer and multi-tool expansion

#### Goal

Prove that the architecture generalizes beyond one consumer and one narrow proof slice.

#### Focus

Phase 4 should test expansion across:

- more than one external consumer shape,
- more than one bridged tool family,
- different local runtime contexts,
- different consumer orchestration patterns,
- different eval-slice profiles.

The purpose of this phase is to test whether Prompt Reforger is truly generic rather than merely successful for the first consumer.

#### Exit criteria

Phase 4 is complete only when all of the following are true:

1. multiple external consumers can use the same generic service contract;
2. more than one bridged tool family has been exercised;
3. the service/harness boundary still holds under expansion;
4. expansion does not force consumer-specific logic back into Orket.

### Phase 5 - Promotion decision

#### Goal

Decide whether the lane should leave incubation and become active canonical authority.

#### Focus

Phase 5 is a governance decision based on the outcomes of the earlier phases.

The promotion decision should evaluate:

- service-contract stability,
- live-proof strength,
- output-surface stability,
- bundle and drift semantics,
- boundary stability between service and external harnesses,
- whether consumers use the service without reintroducing app-specific Orket behavior.

#### Exit criteria

Phase 5 is complete only when one of the following outcomes is recorded explicitly:

- the lane is promoted into active roadmap/spec flow,
- the lane remains incubating with explicit blockers,
- the lane is narrowed, split, or paused with explicit reasons.

## 22. Multi-phase guardrails

The following guardrails apply across all future phases:

1. Prompt Reforger must remain a generic Orket service surface.
2. External consumers must remain responsible for consumer-specific orchestration, bridge ownership, eval ownership, and matrix truth.
3. Shared result vocabulary must not collapse the service/harness authority split.
4. Unsupported remains a valid truthful outcome in every phase.
5. A compatibility bundle may be frozen only for qualifying runs.
6. Expansion must not silently reintroduce LocalClaw-specific behavior into Orket.