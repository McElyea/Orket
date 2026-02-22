# Orket Sovereign Infrastructure Plan

Status: Active execution (Card 13 landed)
Scope root: `docs/projects/modularize/`
Implementation scope: Sentinel guardrail + CI workflows + modularize doc alignment

## 1) Objectives

1. Implement a deterministic CI guardrail (`tools/ci/orket_sentinel.py`) that fail-closes on diff unavailability.
2. Enforce Triple-Lock for triplets under `data/dto` only.
3. Validate non-triplet changed JSON files via parse-only checks.
4. Standardize deterministic single-line CI diagnostics with machine-parseable fields.
5. Align living modularize docs with operational behavior (without changing artifact hashes, package identity, or stage model).

## 2) Authoritative Requirements Snapshot

1. Triplet soil: `data/dto`.
2. Triplet members:
`<stem>.body.json`, `<stem>.links.json`, `<stem>.manifest.json`.
3. Triple-Lock enforcement:
strict for triplets under `data/dto` only.
4. Diff behavior:
fail closed with `E_DIFF_UNAVAILABLE` if diff cannot be computed.
5. Logging contract:
single-line event format, stable ordering, deterministic details serialization.
6. Stage model:
five-stage only (`base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`).
7. No changes to:
published hashes, grand seal, package version, stage order, JSON artifacts.

## 2.1) Logging + Gatekeeper Hardening Requirements (Normative)

1. Deterministic Pipe Contract:
every emitted event line MUST include `|` even when details are empty.
2. Single-Line Invariant:
message and detail values MUST escape CR/LF (`\r -> \\r`, `\n -> \\n`).
3. Deterministic details:
keys sorted lexicographically; bools as `true`/`false`; `None` as `null`;
dict/list via `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
4. Gatekeeper naming convention:
use `E_<STAGE>_<ERROR>` for new stage failures where feasible without breaking existing consumers.
5. Base-shape wrong-type specificity:
`E_BASE_SHAPE_INVALID_BODY_VALUE` for `/body`,
`E_BASE_SHAPE_INVALID_LINKS_VALUE` for `/links`,
`E_BASE_SHAPE_INVALID_MANIFEST_VALUE` for `/manifest`.

## 3) Constraints and Non-Goals

1. Text/code edits only.
2. Do not mutate integrity-pinned JSON artifact contents.
3. Do not add a typed_reference stage.
4. Do not introduce 6-stage language into living docs.
5. Do not silently skip checks on missing diff context.
6. Non-goal for this pass:
full schema validation for solo JSONs beyond parseability.

## 4) Deliverables

1. `tools/ci/orket_sentinel.py`
2. `.gitea/workflows/orket-sentinel.yml`
4. `docs/projects/modularize/standard.md` updates:
diagnostic logging section and CI root pointer guidance.
5. `docs/projects/modularize/contract-package.md` updates:
rework note and typed enforcement section consistency.
6. `docs/projects/modularize/implementation.md` updates:
raw-id matching algorithm + single-line log format section.

## 5) Work Breakdown Structure

## 5.1 Sentinel Runtime (`tools/ci/orket_sentinel.py`)

1. Build deterministic logger utility:
`emit(level, code, location, message, **details)`.
2. Implement detail formatting rules:
sorted keys, bool normalization, JSON serialization rules, CR/LF escape.
3. Implement summary emitter:
`[SUMMARY] outcome=PASS|FAIL stage=ci errors=<n> warnings=<n>`.
4. Implement git diff acquisition with fail-closed behavior.
5. Implement changed-path classification:
triplet candidates, solo JSON, ignore non-JSON.
6. Implement triplet grouping by stem.
7. Implement strict Triple-Lock validation for each stem.
8. Implement solo JSON parse checks.
9. Aggregate results and exit non-zero on any FAIL.

## 5.2 Git Diff Strategy

1. Resolve base reference from CI env/branch context.
2. Run deterministic diff command.
3. If diff command fails, emit:
`[FAIL] [STAGE:ci] [CODE:E_DIFF_UNAVAILABLE] [LOC:/ci/diff] ...`
4. If diff output is empty:
emit PASS summary with zero errors.
5. Normalize paths to forward-slash style internally.

## 5.3 Triplet Classification Rules

1. Candidate if:
path starts with `data/dto/` and ends with one of:
`.body.json`, `.links.json`, `.manifest.json`.
2. Stem derivation:
remove exactly one recognized suffix.
3. Group changed members by stem.
4. Required set per stem:
`body`, `links`, `manifest`.
5. Incomplete set:
emit `E_TRIPLET_INCOMPLETE` with RFC6901 location and detail lists.

## 5.4 Solo JSON Validation Rules

1. Solo JSON path:
changed `.json` file not identified as triplet candidate.
2. Parse check:
`json.loads(file_contents)`.
3. On parse fail:
emit `E_BASE_SHAPE_INVALID_JSON` at `/ci/schema/<escaped-path>`.
4. On parse success:
emit INFO `"Validated solo JSON parse."`.

## 5.5 RFC6901 Location Rules

1. Pointer roots:
`/ci/diff` and `/ci/schema`.
2. Escape helper:
`~ -> ~0`, `/ -> ~1`.
3. Stem location:
`/ci/diff/<escaped-stem>`.
4. Schema location:
`/ci/schema/<escaped-path>`.

## 5.6 Workflow Integration

1. Create Gitea workflow:
push + pull_request equivalent, full history checkout/fetch, run sentinel.
2. Set env:
`TRIPLELOCK_ROOTS=data/dto`.
3. Keep workflows isolated:
no dependency on unrelated jobs.

## 5.7 Documentation Alignment

1. `standard.md`:
ensure single ASCII pipeline line only.
2. Add `Diagnostic Logging (Normative)` to `standard.md`:
location pointers + single-line deterministic rendering.
3. `contract-package.md`:
remove embedded `propertyNames` pattern line from schema code block if present.
4. Add prose rework note:
relationship label pattern is normative Gatekeeper enforcement.
5. Preserve typed reference enforcement section and mapping tables.
6. `implementation.md`:
ensure raw-id traversal/match algorithm section is exact and explicit.
7. Add `Single-Line Log Format (Normative)` section in `implementation.md`.

## 6) Detailed Execution Sequence

1. Implement logger and shared formatting helpers first.
2. Implement diff acquisition and fail-closed behavior.
3. Implement path classification and grouping.
4. Implement Triple-Lock validation and JSON parse checks.
5. Add summary and exit behavior.
6. Run local smoke checks on synthetic changed-file sets.
7. Add/update Gitea workflow.
8. Patch modularize docs to match implemented behavior.
9. Run static verification grep for:
stage order, forbidden key terms, logging format string, error codes.
10. Final dry-run in both CI contexts if available.

## 7) Suggested Sentinel Module Structure

1. `main()`
2. `resolve_diff_base()`
3. `get_changed_files(base_ref)`
4. `classify_paths(changed_paths, tripleroots)`
5. `group_triplets(triplet_candidates)`
6. `validate_triplets(grouped)`
7. `validate_solo_json(paths)`
8. `to_pointer_token(value)`
9. `format_details(details)`
10. `emit(...)`, `emit_summary(...)`

## 8) Deterministic Logging Contract (Implementation Guidance)

Event line format:
`[LEVEL] [STAGE:ci] [CODE:<code>] [LOC:<location>] <message> | <sorted k=v pairs>`

1. `LEVEL` in `{INFO, FAIL}`.
2. `STAGE` fixed as `ci`.
3. `CODE` stable machine token.
4. `LOC` RFC6901 pointer.
5. Message CR/LF escaped as `\\r` and `\\n`.
6. Detail keys sorted lexicographically.
7. Bool values rendered as `true`/`false`.
8. Dict/list details serialized with:
`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
9. Summary line always emitted once.

## 9) Error and Info Codes

Required FAIL codes:

1. `E_DIFF_UNAVAILABLE`
2. `E_TRIPLET_INCOMPLETE`
3. `E_BASE_SHAPE_INVALID_JSON`

Recommended INFO codes:

1. `I_TRIPLET_COMPLETE`
2. `I_SOLO_JSON_VALID`
3. `I_DIFF_READY`
4. `I_NO_RELEVANT_JSON`

## 10) Validation and Test Strategy

## 10.1 Unit-Level (script behavior)

1. Diff unavailable path returns FAIL summary and exit 1.
2. Mixed changed files classify correctly.
3. Triplet complete emits INFO.
4. Triplet incomplete emits FAIL with missing list.
5. Solo JSON parse pass emits INFO.
6. Solo JSON parse fail emits FAIL.
7. RFC6901 escaping correctness for `/` and `~`.
8. Deterministic detail ordering and bool rendering.

## 10.2 Integration-Level (workflow behavior)

1. Gitea workflow triggers on push and PR equivalent.
2. Full-history fetch prevents shallow diff failures in normal operation.
3. Sentinel non-zero exit fails workflow.

## 10.3 Regression Checks

1. No change to package version text.
2. No change to grand seal text.
3. No change to stage order text.
4. No living-doc introduction of typed_reference stage language.

## 11) Rollout and Risk Controls

1. Start with strict fail-closed behavior enabled immediately.
2. Keep log output minimal but deterministic for machine parsing.
3. Do not couple sentinel with unrelated quality jobs.
4. If high false positives occur:
adjust classification logic only, not fail-closed principle.

## 12) Stop-Ship Criteria

1. Sentinel passes when diff is unavailable.
2. Sentinel skips incomplete triplets under `data/dto`.
3. Sentinel log lines violate deterministic format.
4. Workflow lacks full-history checkout/fetch.
5. Living docs drift from implemented behavior.
6. Any introduced text implies 6-stage pipeline or typed_reference stage.

## 13) Implementation Checklist

1. Add sentinel script with executable main.
2. Wire `.gitea/workflows/orket-sentinel.yml` with `TRIPLELOCK_ROOTS=data/dto`.
3. Patch `standard.md` diagnostic logging section.
4. Patch `contract-package.md` rework note + schema block adjustment.
5. Patch `implementation.md` raw-id + log-format sections.
6. Run local script sanity checks.
7. Capture sample PASS and FAIL outputs.
8. Prepare concise commit summary and verification notes.

## 14) Helpful Guidelines for Reviewers

1. Validate behavior, not prose:
run sentinel against crafted diffs.
2. Verify fail-closed branch explicitly.
3. Check pointer escaping in emitted locations.
4. Confirm `data/dto`-only strict Triple-Lock scope.
5. Confirm no JSON artifact changes in the diff.
6. Confirm no hash/identity field churn in docs.
7. Confirm deterministic ordering in detail payloads.

## 15) Post-Implementation Maintenance

1. Keep error code set stable for CI consumers.
2. Version logging format only if breaking changes are required.
3. Add new triplet soils only by explicit roadmap decision.
4. Expand solo JSON validation to schema checks only in a separate planned phase.

## 16) Execution Cards (Detailed)

Use these cards as the day-to-day execution units.
Definition of Done for each card:
1. Code/doc changes are complete and deterministic.
2. Acceptance criteria pass.
3. No prohibited drift is introduced (hash/package/stage model constraints).

### Card 01: Sentinel Skeleton and Logger Contract

Objective:
Create the sentinel entrypoint and deterministic single-line logger primitives.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Add script entrypoint (`main()`), argument/env loading, and result accumulator.
2. Add logger with strict format:
`[LEVEL] [STAGE:ci] [CODE:<code>] [LOC:<location>] <message> | <sorted k=v pairs>`
3. Add summary line:
`[SUMMARY] outcome=PASS|FAIL stage=ci errors=<n> warnings=<n>`

Implementation notes:
1. Keep all emitted lines single-line.
2. Escape message CR/LF as `\\r` and `\\n`.
3. Sort detail keys lexicographically.
4. Render bool as `true`/`false`.
5. Render dict/list via compact deterministic JSON:
`json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
6. Always emit the pipe delimiter (`|`) even when details are empty.
7. Escape CR/LF in message and all detail values.
8. Render `None` as `null`.

Acceptance criteria:
1. Emits correctly formatted INFO and FAIL lines.
2. Emits exactly one SUMMARY line.
3. Formatting output remains stable across runs.
4. Every event line contains the delimiter and stays single-line.

Test checklist:
1. Unit test logger formatting with mixed detail types.
2. Verify key ordering and escaped newline behavior.
3. Verify summary line emitted for both pass/fail paths.

Rollback:
1. Keep previous logger helper shape isolated; revert only logger functions if needed.

### Card 02: Diff Acquisition (Fail-Closed)

Objective:
Implement deterministic changed-file discovery and hard-fail when unavailable.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Resolve base ref from CI context/env.
2. Compute changed files via `git diff`.
3. If unavailable (missing refs, shallow history, command failure), emit:
`E_DIFF_UNAVAILABLE` at `/ci/diff` and exit FAIL.

Implementation notes:
1. Do not silently pass when diff is unavailable.
2. Normalize paths to forward slashes for downstream logic.
3. Keep diff acquisition deterministic and minimal (no fallback heuristics that can mask failures).

Acceptance criteria:
1. Normal case returns stable changed-path list.
2. Missing base/ref path emits required FAIL code/location.
3. Non-zero exit on diff failure path.

Test checklist:
1. Simulate missing base ref.
2. Simulate git command failure.
3. Simulate no-diff scenario and verify PASS summary.

Rollback:
1. Revert base-ref resolution logic only; preserve logger and summary behavior.

### Card 03: Path Classification (Triplet Candidates vs Solo JSON)

Objective:
Classify changed files exactly per policy.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Triplet candidate:
changed path under `data/dto` ending with `.body.json`, `.links.json`, or `.manifest.json`.
2. Solo JSON:
changed `.json` not part of triplet candidate.
3. Ignore non-JSON files.

Implementation notes:
1. Use suffix match with exact endings.
2. Keep classification pure (no file reads here).
3. Keep result structures deterministic (sorted lists).

Acceptance criteria:
1. Correct partition for mixed changed sets.
2. No false positives outside `data/dto` for triplets.

Test checklist:
1. Add cases for nested `data/dto/...`.
2. Add cases for `.json` files outside `data/dto`.
3. Add cases with non-JSON files.

Rollback:
1. Revert classification helper without touching diff/logger.

### Card 04: Triple-Lock Grouping and Enforcement

Objective:
Enforce strict 3-member membership for every changed triplet stem.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Stem derivation by stripping one recognized suffix.
2. Group by stem.
3. Require all of:
`.body.json`, `.links.json`, `.manifest.json`.
4. On incomplete stem emit:
`E_TRIPLET_INCOMPLETE`, location `/ci/diff/<escaped-stem>`, details `changed=[...]`, `missing=[...]`.
5. On complete stem emit INFO line.

Implementation notes:
1. RFC6901 token escape for `<stem>` (`~` then `/`).
2. Keep `changed` and `missing` detail arrays sorted.

Acceptance criteria:
1. Incomplete stems fail deterministically.
2. Complete stems produce INFO.
3. Location pointers are correctly escaped.

Test checklist:
1. Single-member, two-member, and complete-member scenarios.
2. Stem containing `/` and `~` characters.

Rollback:
1. Revert stem grouping/validation functions only.

### Card 05: Solo JSON Parse Validation

Objective:
Parse-validate solo JSON files and emit deterministic diagnostics.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. For each solo JSON path, read and `json.loads`.
2. Parse failure:
emit `E_BASE_SHAPE_INVALID_JSON` at `/ci/schema/<escaped-path>`.
3. Parse success:
emit INFO `"Validated solo JSON parse."`.

Implementation notes:
1. Use UTF-8 reads.
2. Pointer-escape full path token for location.

Acceptance criteria:
1. Invalid JSON reliably fails with required code/location.
2. Valid JSON produces INFO and no error increment.

Test checklist:
1. Malformed JSON example.
2. Valid minified and pretty JSON examples.

Rollback:
1. Revert parse loop only; preserve classification and triplet checks.

### Card 06: Final Decision and Exit Policy

Objective:
Finalize sentinel outcome logic and process exit behavior.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Aggregate FAIL events as errors count.
2. Always emit one summary.
3. Exit code:
non-zero if any FAIL, zero otherwise.

Implementation notes:
1. Keep warnings count stable (zero unless explicitly introduced later).
2. Do not conflate INFO with warning.

Acceptance criteria:
1. PASS path exits 0 with summary outcome PASS.
2. FAIL path exits non-zero with summary outcome FAIL.

Test checklist:
1. No-relevant-json run.
2. One failing triplet.
3. One failing solo parse.

Rollback:
1. Revert only outcome/exit function.

### Card 07: Gitea Workflow Wiring

Objective:
Wire sentinel into local Gitea automation with full history.

Files:
1. `.gitea/workflows/orket-sentinel.yml`

Scope:
1. Trigger parity with push/PR behavior as supported.
2. Ensure full history fetch/checkout.
3. Run `python3 tools/ci/orket_sentinel.py`.
4. Set env `TRIPLELOCK_ROOTS=data/dto`.

Acceptance criteria:
1. Gitea runner executes sentinel.
2. Sentinel failure fails workflow.

Test checklist:
1. PR with incomplete triplet fails.
2. PR with complete triplet and valid solo JSON passes.

Rollback:
1. Revert only `.gitea/workflows/orket-sentinel.yml`.

### Card 08: Gitea Workflow Validation

Objective:
Validate Gitea sentinel workflow behavior and reproducibility.

Files:
1. `.gitea/workflows/orket-sentinel.yml`

Scope:
1. Trigger parity with push/PR behavior as supported.
2. Ensure full history fetch/checkout.
3. Run `python3 tools/ci/orket_sentinel.py`.
4. Set env `TRIPLELOCK_ROOTS=data/dto`.

Acceptance criteria:
1. Gitea runner executes sentinel.
2. Failure semantics are stable across repeated runs.

Test checklist:
1. Same failing/passing fixtures used for repeated Gitea runs.

Rollback:
1. Revert only `.gitea/workflows/orket-sentinel.yml`.

### Card 09: `standard.md` Logging and Pointer Normatives

Objective:
Align standard with CI/diagnostic contract.

Files:
1. `docs/projects/modularize/standard.md`

Scope:
1. Keep single ASCII pipeline line only.
2. Add Diagnostic Logging (Normative) section covering:
location as RFC6901 JSON pointer,
roots `/body`, `/links`, `/manifest`, `/package`, `/ci/diff`, `/ci/schema`,
single-line sorted k/v rendering requirements.

Acceptance criteria:
1. Logging contract in standard is explicit and implementation-aligned.
2. No 6-stage or typed_reference stage language appears.

Rollback:
1. Revert only the added section if wording disputes occur.

### Card 10: `contract-package.md` Vocabulary + Typed Mapping Governance

Objective:
Finalize package prose so enforcement intent is explicit without mutating pinned JSON artifacts.

Files:
1. `docs/projects/modularize/contract-package.md`

Scope:
1. Keep inventory note clarifying 14 listed vs 11 integrity-pinned artifacts.
2. Add rework prose before vocabulary schema block:
relationship label pattern is normative Gatekeeper enforcement.
3. Keep Typed Reference Enforcement (Normative) section and complete mapping tables.
4. Do not modify hashes, package version, stage order, or JSON artifact data.

Acceptance criteria:
1. Typed key->type mapping is complete for both DTOs.
2. Prose and embedded blocks are consistent with living rules.

Rollback:
1. Revert prose-only edits, preserve mapping tables.

### Card 11: `implementation.md` Raw-ID + Log Format Normatives

Objective:
Ensure implementation doc is executable as policy text.

Files:
1. `docs/projects/modularize/implementation.md`

Scope:
1. Keep Raw-ID Policy Matching Algorithm (Normative) with exact traversal and match rules.
2. Add Single-Line Log Format (Normative) matching sentinel logger contract.
3. Keep legacy mapping note for `E_TYPED_REF_MISMATCH` in `dto_links`.

Acceptance criteria:
1. Raw-id behavior is fully specified from living docs alone.
2. Log format section matches sentinel output contract exactly.

Rollback:
1. Revert new section text only.

### Card 12: Final Conformance Audit and Release Gate

Objective:
Run a final doc+runtime conformance pass before merge.

Files:
1. `tools/ci/orket_sentinel.py`
2. `.gitea/workflows/orket-sentinel.yml`
3. `docs/projects/modularize/standard.md`
4. `docs/projects/modularize/contract-package.md`
5. `docs/projects/modularize/implementation.md`

Scope:
1. Validate sentinel outputs against logging contract.
2. Validate Gitea workflow runs sentinel with full history and env set.
3. Re-run modularize drift/audit checklist.
4. Confirm no changes to hashes/grand seal/package version/stage order.

Stop criteria:
1. Any checklist NO on mandatory conformance items.
2. Any sentinel path that can silently pass on diff failure.
3. Any drift between living docs and implemented sentinel behavior.

Acceptance criteria:
1. Checklist all YES for required conformance items.
2. Sentinel produces deterministic logs and summary in pass/fail scenarios.
3. Workflows fail on sentinel FAIL and pass on PASS.

### Card 13: Gatekeeper Wiring (Sentinel Upgrade)

Objective:
Upgrade sentinel to run a Gatekeeper 5-stage pipeline for complete `data/dto` triplets.

Files:
1. `tools/ci/orket_sentinel.py`

Scope:
1. Add a Gatekeeper module/class integrated into sentinel execution.
2. Run stages for complete triplets only:
`base_shape`, `dto_links`, `relationship_vocabulary`, `policy`, `determinism`.
3. `base_shape`:
validate JSON object shapes and reference structure (`type` + `id` required).
4. `dto_links`:
enforce typed mappings for `invocation` and `validation_result`.
5. `relationship_vocabulary`:
validate `(dto_type + relationship + ref_type)` compatibility and cardinality.
6. `policy`:
run recursive Raw-ID traversal on `/body` and `/links`.
7. `determinism`:
validate `order_insensitive` keys against array-valued links keys.
8. Emit stage-scoped FAIL logs with locations rooted in `/body`, `/links`, or `/manifest`.
9. Sort Gatekeeper FAIL emissions deterministically by stage then pointer.

Acceptance criteria:
1. Complete triplets execute the full 5-stage Gatekeeper pipeline.
2. Stage name in emitted events is one of:
`base_shape`, `dto_links`, `relationship_vocabulary`, `policy`, `determinism`.
3. Gatekeeper failures are deterministic in ordering for repeated runs on the same input.
4. Existing CI summary semantics remain unchanged.

Verification:
1. `python -m py_compile tools/ci/orket_sentinel.py`
2. `$env:BASE_REF='HEAD'; python tools/ci/orket_sentinel.py`

Status:
1. Completed in commit `dd7c390`.
2. Post-landing hardening:
new Gatekeeper error codes should follow `E_<STAGE>_<ERROR>` without breaking existing consumers.

### Card 14: Sovereign Logging Hardening

Objective:
Eliminate conditional delimiters and newline-injection risk in CI logs; tighten base-shape code specificity.

Files:
1. `tools/ci/orket_sentinel.py`
2. `docs/projects/modularize/standard.md`
3. `docs/projects/modularize/implementation.md`

Scope:
1. Enforce unconditional `|` delimiter emission for all event lines.
2. Escape CR/LF in message and all detail values.
3. Ensure `None` details render as `null`.
4. Split base-shape wrong-type codes by root:
`E_BASE_SHAPE_INVALID_BODY_VALUE`,
`E_BASE_SHAPE_INVALID_LINKS_VALUE`,
`E_BASE_SHAPE_INVALID_MANIFEST_VALUE`.
5. Keep `E_POLICY_RAW_ID_FORBIDDEN` as normative exemplar for stage-scoped naming.

Acceptance criteria:
1. Multi-line exception/detail inputs still produce single-line logs.
2. Every emitted event line includes `|` exactly once as delimiter.
3. `/body` and `/manifest` wrong-type failures do not use `E_BASE_SHAPE_INVALID_LINKS_VALUE`.
4. Docs explicitly capture unconditional delimiter + newline-safe detail behavior.

Verification:
1. `python -m py_compile tools/ci/orket_sentinel.py`
2. `$env:BASE_REF='HEAD'; python tools/ci/orket_sentinel.py`
3. Targeted run with synthetic newline-containing detail/message payloads.

Status:
1. In progress.

## 17) Progress Updates

1. 2026-02-22: Card 13 implemented and pushed in `dd7c390`.
2. Gatekeeper pipeline added to `tools/ci/orket_sentinel.py` with deterministic stage/pointer failure ordering.
3. Local compile + smoke checks passed.
4. 2026-02-22: Card 14 started for unconditional delimiter, newline-safe details, and base-shape code split.
