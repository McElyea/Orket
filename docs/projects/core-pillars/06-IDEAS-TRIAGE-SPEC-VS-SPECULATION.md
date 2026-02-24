# Ideas Triage: Spec vs Speculation

Date: 2026-02-24  
Status: active  
Source: `docs/projects/ideas/Ideas.md` extraction pass

## Spec-Grade Items Promoted
1. Command safety transaction loop:
- plan -> snapshot -> execute -> verify -> finalize/revert
- promoted to `04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`

2. Scoped write barrier:
- hard fail for out-of-scope writes
- promoted to `04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`

3. Mutating command contracts for `init`, `api add`, `refactor`, `swap`:
- promoted to `04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`

4. Stable safety error-code set:
- promoted to `04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`

5. Bucket D failure-lesson memory:
- promoted to `05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`

6. Deterministic classifier tags and D1-D4 acceptance tests:
- promoted to `05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`

## Speculation/Advisory Items Deferred
1. Model-assisted tagging for failure classification:
- defer to post-v1 optional enhancement

2. Migration from JSONL to SQLite:
- defer until operational need justifies complexity

3. Cross-machine sync and heavy replay/attestation concepts:
- out of v1 scope

4. General narrative positioning content:
- excluded as non-normative chatter

## Implementation References (Informative, Non-Normative)
1. P0 transaction shell snippets in ideas doc:
- treated as reference implementation hints, not canonical contract
- production behavior must be validated by project requirements and acceptance tests

2. Codex brief language:
- treated as execution guidance only

## Disposition
1. `ideas/Ideas.md` remains intake-retired and should not carry active requirements.
2. Active requirements now live under `docs/projects/core-pillars/`.
