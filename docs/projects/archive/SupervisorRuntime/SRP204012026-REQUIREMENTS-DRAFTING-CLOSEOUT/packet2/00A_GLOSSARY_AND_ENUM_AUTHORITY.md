# SupervisorRuntime Packet 2 Glossary And Enum Authority
Last updated: 2026-04-01
Status: Completed archived draft glossary authority
Owner: Orket Core
Packet role: Shared draft vocabulary

## Core nouns

1. `Principal`
   - one of: `human_operator`, `model`, `scheduler`, `rule_engine`, `extension`, `external_service`
2. `Capability`
   - a named privileged action class with caller, scope, timeout, approval, and audit rules
3. `Admission`
   - the governed act that accepts or denies a run against declared inputs and policy
4. `Run`, `Attempt`, `Step`
   - canonical execution identity hierarchy
5. `Reservation`, `Lease`, `Resource`
   - reservation is admission or claim truth, lease is active ownership truth, resource is governed target truth
6. `EffectJournalEntry`
   - normative mutation and closure-relevant write publication
7. `Checkpoint`, `CheckpointAcceptance`, `RecoveryDecision`
   - explicit supervisor-owned recovery family
8. `OperatorAction`
   - first-class operator command, risk acceptance, or attestation record family
9. `Reconciliation`
   - first-class divergence-handling authority family
10. `FinalTruth`
   - sole intended terminal closure authority
11. `Namespace`
   - explicit scope boundary for mutation, ownership, and child composition
12. `TriggerClass`
   - admitted run-start source such as direct operator, scheduler, event, or policy trigger

## Draft enum stance

Packet 2 draft docs may name enum families, but they must:
1. reuse existing active authority nouns where they already exist
2. avoid inventing parallel labels for Packet 1 or ControlPlane vocabulary
3. mark any still-unsettled family as draft rather than shipped
