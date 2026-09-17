# Epic Run Admission Before Initialization

## Summary
- Change title: Reserve standard epic resources before initialization can race.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contract: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta
- Before: callers can both pass recovery checks before a ledger exists, then reset
  cards or dispatch competing workloads under the same session or shared resources.
- After: application admission retains an immutable run/owner/request/resource
  claim in the existing publication journal before initialization. Same-session
  claims and overlapping active resources reject before writes. Verified complete
  publication releases the reservation while retaining its history.
- New internal schema: `epic_run_admission.v1`, with active/released states.
- New run artifacts retain the original admission digest/owner reference;
  preparation/publication validates it before further completion effects.
- No timeout-based takeover, new retry authority or inferred workload outcome is
  introduced. Independent journals and arbitrary writers remain outside this gate.

## Migration Plan
1. Add the admission table through the journal's normal initialization.
2. New standard entries require a fresh admission. Existing retained publication
   recovery remains valid without inventing an old admission record.
3. Prove races before initialization, process death before a ledger exists,
   conflicting resources, unchanged evidence on refusal and release only after
   verified publication. Keep disjoint resources admissible.
4. Refresh composed source and live llama.cpp proof; disclose installed proof limits.

## Rollback Plan
1. Stop competing entry if reservations fail to exclude writers or release without
   verified publication. Preserve admission and effect history for repair.
2. Do not clear interrupted claims or treat a new session as owner recovery.

## Versioning Decision
- Effective date: 2026-09-12; new internal admission contract, no production
  migration, source commit or release performed in this worktree.
