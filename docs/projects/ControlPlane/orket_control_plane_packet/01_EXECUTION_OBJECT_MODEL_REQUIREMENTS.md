# Execution Object Model Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation

## Purpose

Define the minimum first-class execution objects required for Orket's control plane so lifecycle, recovery, capability checks, reservations, leases, reconciliation, operator actions, effect journal publication, and checkpoint acceptance all refer to the same nouns.

## Authority note

Shared nouns and enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

This document defines object shape, relationships, and object-specific requirements.

## Design principle

An execution object is first-class only if at least one of the following is true:
1. lifecycle transitions depend on it
2. authority or capability checks depend on it
3. failure or recovery classification depends on it
4. reconciliation depends on it
5. operator inspection or action depends on it
6. durable proofs must refer to it

## Required execution objects

### EO-01. Workload

A workload is the durable definition of a governed executable unit.

A workload must define at minimum:
1. stable workload identifier
2. version or digest surface
3. declared capabilities
4. declared namespace or scope rules
5. declared resource classes it may own or request
6. declared degraded modes, if any
7. input contract
8. output contract
9. recovery policy references
10. reconciliation requirements, if any

A workload is not an attempt and is not a single run result.

### EO-02. Run

A run is a specific execution instance of a workload under resolved policy and resolved configuration.

A run must carry at minimum:
1. run identifier
2. parent workload identifier
3. workload version or digest
4. resolved policy snapshot reference and digest
5. resolved configuration snapshot reference and digest
6. creation timestamp
7. admission decision receipt
8. current lifecycle state using glossary enums
9. current attempt reference if execution has started
10. final truth record reference when closed

A run is the authoritative container for attempts, effects, reservations, leases, checkpoints, and final closure truth.

### EO-03. Attempt

An attempt is a bounded execution try within a run.

An attempt must carry at minimum:
1. attempt identifier
2. parent run identifier
3. attempt ordinal
4. attempt state using glossary enums
5. starting state snapshot reference
6. start timestamp
7. end timestamp if closed
8. side-effect boundary classification if failed or interrupted
9. failure classification if failed
10. recovery decision reference if a subsequent action is authorized

Attempts are required because recovery must not overwrite the history of prior execution tries.

### EO-04. Step

A step is a logically bounded execution segment within an attempt.

A step must carry at minimum:
1. step identifier
2. parent attempt identifier
3. step kind
4. input reference
5. output reference
6. capability used, if any
7. resources touched, if any
8. observed result classification
9. receipt references
10. closure classification

Step granularity must be sufficient to support failure localization and replay reasoning, but must not devolve into unhelpful implementation-detail trace spam.

### EO-05. Effect

An effect is the control-plane record of an authorized action that may change state inside or outside Orket.

An effect must carry at minimum:
1. effect identifier
2. parent step identifier
3. effect class using glossary enums
4. capability class used
5. intended target
6. idempotency class
7. preconditions reference
8. authorization basis
9. observed result reference
10. uncertainty class

The effect object is distinct from a tool call record.
A tool call may have zero, one, or multiple effect records depending on the governed surface.

### EO-05A. Effect journal entry

An effect journal entry is the append-only authority publication of effect truth.

An effect journal entry must carry at minimum:
1. journal entry identifier
2. parent effect identifier
3. parent run, attempt, and step references
4. authorization basis reference
5. publication sequence
6. publication timestamp
7. intended target reference
8. observed result reference when available
9. uncertainty classification
10. integrity linkage strong enough to verify append-only ordering

### EO-06. Resource

A resource is any durable or semi-durable entity whose ownership or state matters to execution truth or recovery.

A resource must carry at minimum:
1. resource identifier
2. resource kind
3. namespace or scope
4. ownership class
5. current observed state
6. last observed timestamp
7. cleanup authority class
8. provenance reference
9. reconciliation status
10. orphan classification when applicable

### EO-07. Reservation

A reservation is a pre-execution claim on capacity, resource scope, or concurrency scope.

A reservation must carry at minimum:
1. reservation identifier
2. holder reference
3. reservation kind class
4. target scope or resource reference
5. creation timestamp
6. expiry or invalidation basis
7. current status
8. promotion rule to lease if applicable
9. release or invalidation history
10. supervisor authority reference

Reservation is not ownership.

### EO-08. Lease

A lease is the time- and authority-bounded right for a run or attempt to own or mutate a resource.

A lease must carry at minimum:
1. lease identifier
2. resource identifier
3. holder reference
4. lease epoch
5. granted timestamp
6. lease publication timestamp
7. expiry or TTL basis
8. current status
9. last confirmed observation
10. revocation or transfer history
11. cleanup eligibility rules

Lease objects are mandatory where resource ownership must survive crashes, retries, or reconciliation.
Lease publication must be append-only so a stable `lease_id` can retain durable history across renewal, expiry, uncertainty, and verified release.

### EO-09. Checkpoint

A checkpoint is a durable resumption boundary accepted by the runtime.

A checkpoint must carry at minimum:
1. checkpoint identifier
2. parent run or attempt reference
3. creation timestamp
4. state snapshot reference
5. resumability class
6. invalidation conditions
7. dependent resources
8. dependent effects or journal range
9. policy digest
10. integrity verification reference

Not every run requires checkpoints, but a control plane that supports meaningful recovery must have a defined checkpoint vocabulary.

### EO-09A. Checkpoint acceptance record

A checkpoint acceptance record is the supervisor-owned publication of checkpoint admissibility.

A checkpoint acceptance record must carry at minimum:
1. acceptance record identifier
2. parent checkpoint identifier
3. supervisor authority reference
4. decision timestamp
5. acceptance or rejection outcome
6. resulting resumability class
7. required re-observation class
8. policy compatibility basis
9. dependent effect journal references
10. dependent reservation or lease references

### EO-10. Recovery decision

A recovery decision is the durable control-plane authorization for post-failure action.

A recovery decision must carry at minimum:
1. decision identifier
2. parent run and failed attempt reference
3. failure classification basis
4. side-effect boundary classification
5. recovery policy reference
6. authorized next action from the glossary recovery action vocabulary
7. authorized execution mode if workload execution may continue
8. target checkpoint or target attempt reference if applicable
9. required observations or reconciliation preconditions
10. rationale reference

If a recovery decision authorizes continued workload execution, it must state whether it:
1. resumes an existing attempt
2. starts a new attempt

### EO-11. Reconciliation record

A reconciliation record is the authoritative result of comparing durable intended state against observed state.

A reconciliation record must carry at minimum:
1. reconciliation identifier
2. target run or resource set
3. comparison scope
4. observed resources or effects
5. intended resources or effects
6. divergence classification
7. residual uncertainty classification
8. publication timestamp
9. resulting safe continuation class
10. operator requirement if applicable

### EO-12. Operator action

An operator action is an explicit recorded human input into the control plane.

An operator action must carry at minimum:
1. action identifier
2. actor reference
3. input class using glossary enums
4. target object
5. timestamp
6. precondition basis
7. result
8. affected lifecycle transitions
9. affected reservations, leases, or resources
10. resulting receipt references

### EO-13. Final truth record

A final truth record is the authoritative closure surface for a run.

A final truth record must carry at minimum:
1. final truth record identifier
2. parent run identifier
3. result class using the architecture result vocabulary
4. completion classification
5. evidence sufficiency classification
6. residual uncertainty classification
7. degradation classification
8. closure basis classification
9. terminality basis classification
10. authority source set

## Required object relationships

### EO-14. Referential integrity

The object model must support authoritative relations at minimum between:
1. workload -> run
2. run -> attempt
3. attempt -> step
4. step -> effect
5. effect -> effect journal entry
6. run -> reservation
7. reservation -> lease when promotion occurs
8. lease -> resource
9. run or attempt -> checkpoint
10. checkpoint -> checkpoint acceptance record
11. failed attempt -> recovery decision
12. run or resource scope -> reconciliation record
13. operator action -> affected objects
14. run -> final truth record

### EO-15. Immutable history with append-only control truth

Historical attempts, effects, reconciliation records, operator actions, and final truth publications must be append-only.
Historical effect journal entries and checkpoint acceptance records must also be append-only.
Later corrections may supersede interpretation but must not rewrite previously published control-plane history.

### EO-16. Object identity must survive replay and recovery

Identity rules must be strong enough that:
1. retries do not erase prior attempts
2. reservation and lease ownership remain reconstructable
3. reconciliation can compare across attempts
4. operator commands remain attributable
5. final truth surfaces can explain the path taken

## Object classes explicitly not treated as first-class

The following may exist as implementation details but are not first-class control-plane objects unless later promoted:
1. raw prompt template
2. internal planner scratchpad
3. model explanation text
4. UI view state
5. convenience cache entries with no authority implications

## Acceptance criteria

The execution object model is acceptable only when:
1. every lifecycle transition names its target object and source object unambiguously
2. every recovery decision references a failed attempt rather than vague run state
3. reservation and lease are distinct first-class objects with explicit progression
4. effect uncertainty can be expressed without ambiguity
5. resource ownership survives partial failure
6. reconciliation, checkpoint acceptance, and final truth can be published without inventing hidden object types
