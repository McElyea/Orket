# Requirement Refactor Loop Template

Date:
Facilitator:
Recorder:
Attendees:
Timebox: 90 minutes

## 1) Scope Lock (00-10 min)
In Scope:
- WorkItem core contract
- Workflow profiles
- Gate policy boundaries

Out of Scope:
- UI/UX polish
- Non-core modules
- Performance tuning
- Naming bikeshedding

## 2) Core Contract Decisions (10-30 min)
Proposed fields:
- `id`
- `kind`
- `parent_id`
- `status`
- `assignee`
- `requirements_ref`
- `verification_ref`
- `metadata`
- `created_at`
- `updated_at`

Invariants:
- [ ] Invariant 1:
- [ ] Invariant 2:
- [ ] Invariant 3:

Decisions:
1. Decision:
- Status: accepted | deferred | rejected
- Rationale:
- Impact:
- Test required:

## 3) Workflow Profiles (30-55 min)
### `legacy_cards_v1`
States:
Allowed transitions:
Terminal states:
Illegal transitions:

### `default_profile_v1`
States:
Allowed transitions:
Terminal states:
Illegal transitions:

Decisions:
1. Decision:
- Status: accepted | deferred | rejected
- Rationale:
- Test required:

## 4) Gate Policy Boundaries (55-75 min)
Gate checks run:
- pre-transition:
- post-transition:

Deterministic failure codes:
- CODE_1:
- CODE_2:

Required gate payload contract:
- field_1:
- field_2:

Decisions:
1. Decision:
- Status: accepted | deferred | rejected
- Rationale:
- Test required:

## 5) Migration Contract
Legacy mapping rules:
- Rock -> ?
- Epic -> ?
- Issue -> ?

Backfill rules:
Rollback rules:

Decisions:
1. Decision:
- Status: accepted | deferred | rejected
- Rationale:
- Test required:

## 6) Implementation Cut (75-90 min)
Tickets:
1. Ticket:
- Owner:
- Files:
- Acceptance tests:

2. Ticket:
- Owner:
- Files:
- Acceptance tests:

Deferred items:
1. Item:
- Reason:
- Owner:
- Revisit date:

## 7) Exit Criteria
- [ ] All decisions are accepted, deferred, or rejected (no unresolved items).
- [ ] Every accepted decision has a concrete test plan.
- [ ] Migration rules are documented.
- [ ] Ticket list has owners and acceptance tests.

## Operating Rules
1. If tied after 5 minutes, facilitator decides and records rationale.
2. Any decision without a test plan is automatically deferred.
3. No open-ended "maybe" items carry past session close.
