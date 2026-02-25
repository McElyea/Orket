# Docs Gate Requirements

Date: 2026-02-24  
Status: archived

## Objective
Provide a deterministic docs verification gate for mutation workflows (`orket refine`, CI, and local verify profiles) so broken references and registry drift are blocked before merge.

## Entry Point Contract
1. Command:
- `python scripts/docs_lint.py --project core-pillars`

2. Supported flags (v1):
- `--project <name>` (required for v1 scope, supports `core-pillars`)
- `--root <path>` (default `docs`)
- `--strict` (optional stricter registry behavior)
- `--json` (machine-readable report)

3. Exit codes:
- `0`: pass
- `1`: contract violations found
- `2`: invalid invocation/usage

## Determinism Contract
1. File traversal order must be stable (sorted path order).
2. Violation ordering must be stable (`path`, `check_id`, `detail`).
3. Checks use filesystem + deterministic pattern matching only.
4. No network calls and no non-deterministic time-based logic.

## Check Contracts (v1)
1. `DL1` Relative Link Integrity:
- Scan markdown under `docs/projects/core-pillars/`.
- Validate relative links and image paths.
- Ignore `http://`, `https://`, `mailto:`, and pure `#anchor` links.
- For `file.md#anchor`, validate file existence only in v1.

2. `DL2` Canonical Registry Presence:
- Canonical files listed by the project registry must exist on disk.
- Missing canonical path is a hard fail.

3. `DL3` Active Doc Header Integrity:
- For docs where `Status: active` appears within first 40 lines, require:
- `Date:`
- `Status:`
- `## Objective`

4. `DL4` Strict Cross-Reference Integrity (`--strict`):
- Validate that referenced error-code tokens (`E_[A-Z0-9_]+`) are declared in canonical contract files.
- Validate that referenced acceptance tokens (`A*`, `D*`, `API-*`) are declared in canonical contract files.
- Validate active-doc registry coverage in strict mode.

## Error Code Contract
1. `E_DOCS_LINK_MISSING`
2. `E_DOCS_CANONICAL_MISSING`
3. `E_DOCS_HEADER_MISSING`
4. `E_DOCS_CROSSREF_MISSING`
5. `E_DOCS_USAGE`

## Output Contract
1. Human output:
- Deterministic list of violations with check id, path, and reason.
- Final summary line with pass/fail and violation count.

2. JSON output (`--json`):
- `status`: `PASS|FAIL`
- `project`
- `checked_files`
- `violation_count`
- `violations`: ordered array of `{code, check_id, path, message}`

## Acceptance Gates
1. `DL1` broken link fixture fails with `E_DOCS_LINK_MISSING`.
2. `DL2` missing canonical file fails with `E_DOCS_CANONICAL_MISSING`.
3. `DL3` malformed active-doc header fails with `E_DOCS_HEADER_MISSING`.
4. `DL4` strict mode undeclared token fails with `E_DOCS_CROSSREF_MISSING`.
5. `DL0` baseline clean pass emits zero violations.

## Non-Goals (v1)
1. Markdown anchor-existence verification.
2. Link checks outside project scope.
3. AI-based prose grading.
4. Auto-fix mode.
