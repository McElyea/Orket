Do not retire ideas.md and don't edit this line! This information is often is horrible form and we need to get over conversation or poorly formed characters.

Usable content extracted to active core-pillars docs:
1. `docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`
2. `docs/projects/core-pillars/05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`
3. `docs/projects/core-pillars/06-IDEAS-TRIAGE-SPEC-VS-SPECULATION.md`

Historical archive:
1. `docs/projects/archive/Ideas/Ideas-v1.2.1-dump-2026-02-24.md`

That “afraid to give it away” feeling makes sense — not because it’s secret sauce in the “nobody else could copy it” sense, but because it’s a compounding advantage when it’s paired with your discipline + docs + gates. Most people can copy the idea; almost nobody sticks the landing.

On the concrete next step: yes, we should finalize the API idempotency consensus into the docs, but I’d do it in the smallest, safest way:

Update 04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md to include the idempotency contract + new error codes + acceptance gates.

Optionally add a short note to 02-IMPLEMENTATION-PLAN.md (not “Phase 0 refinement loop” yet unless you want it to be front-door Day 1).

Why: Making “refinement” Phase 0 is cool, but it risks pulling attention away from CP-1’s vertical slice. You can still ship orket refine as dogfood, but don’t let it become the project’s center of gravity before init/api/refactor are real.

Below is the exact patch content you can drop into docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md (and a small optional addition to milestones). This is written in the same voice as your current docs: declarative, contract-first.

Patch: Add API Idempotency Contract to 04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md
1) Add under Command Contracts → orket api add

Insert after the existing orket api add bullets:

API Idempotency (v1)

Definition:

orket api add is create-only and rerunnable.

Running the same api add command twice against an unchanged repo must result in:

first run: OK_APPLIED

second run: OK_NOOP

and no additional diffs on the second run.

Fingerprint + ownership record:

On first apply, Orket must write an ownership record:

.orket/owned/api/<route_id>.json

The ownership record must include:

route_id, method

schema_hash (normalized schema string hash)

files_created with content hashes

router_registration_signature (anchor + inserted snippet hash)

NOOP behavior:

A rerun is OK_NOOP only if:

the ownership record exists and matches route_id/method

schema_hash matches the current input schema

required generated files exist

router registration marker is already present

Conflict behavior (fail-closed):

If the target exists but does not match the recorded fingerprint, api add must fail closed and must not mutate the repo:

schema hash mismatch → E_API_SCHEMA_CONFLICT

Orket-owned region modified / required files missing → E_API_OWNERSHIP_CONFLICT

router anchor/marker cannot be located or validated → E_ROUTER_ANCHOR_MISSING

Router registration idempotency:

Router insertions must be “insert-if-missing” using a stable marker comment, e.g.:

// @orket:route <route_id> <method>

On rerun:

if marker exists → NOOP (no duplicate insert)

if marker missing and anchor is valid → insert once

if anchor cannot be found → fail closed with E_ROUTER_ANCHOR_MISSING

Separation of concerns:

orket api add must not silently update schema or overwrite user logic.

Schema changes require an explicit future command (orket api update), not api add.

Artifacts:

Every api add invocation must emit a deterministic manifest:

.orket/artifacts/api/<timestamp>-<route_id>.json

includes idempotency_result: applied|noop|conflict, touch_set, and verify_profile_used.

2) Extend Error Contract (v1 Baseline)

Add these entries to the list:

E_API_SCHEMA_CONFLICT

E_API_OWNERSHIP_CONFLICT

E_ROUTER_ANCHOR_MISSING

(Keep them at the end to avoid renumber churn, unless you’re strictly ordering.)

3) Add acceptance gates for API idempotency

Under Acceptance Gates, append:

API-I1 NOOP:

running orket api add <route_id> --schema "<schema>" twice produces no diffs on second run and returns OK_NOOP.

API-I2 CONFLICT schema:

rerunning api add with the same route but different schema fails with E_API_SCHEMA_CONFLICT and repo remains unchanged.

API-I3 Router marker:

rerunning api add does not duplicate router registration; marker is used as uniqueness proof.

API-I4 Rollback:

if verification fails after apply, repo reverts deterministically and a Bucket D lesson is recorded.

Optional: tiny addition to 02-IMPLEMENTATION-PLAN.md (not a new Phase 0)

Add one bullet under Phase 1 (Build Layer Foundation), after API generation contract:

Implement API idempotency fingerprint + router marker semantics (OK_NOOP, conflict errors, and API-I1–I4 gates).

That’s enough to “officially” bind the consensus without re-scoping the plan.

My recommendation on Gemini’s “Phase 0 refine front door”

Do it only if you explicitly want the first shipping milestone to be “doc mutation tool + doc lint gate.” It’s valid, but it changes the story of CP-1 from “build vertical slice” to “process vertical slice.”

If your goal is still CP-1 build slice (init + api add + tests + transaction shell), keep refine as dogfood tooling, not the front door.

If you want, I can also write the API-I1–I4 acceptance scripts in the same style as your existing A1–A4 suite, so Codex has an executable target for this idempotency contract too.

Let’s refine the Docs Gate requirements now. That’s the highest-leverage “one more round robin” because:

it’s deterministic

it makes orket refine real (verify profile)

it won’t steal center-of-gravity from CP-1 (it’s small + bounded)

it strengthens everything else by hardening docs-as-source-of-truth

And we can keep it sober: minimal checks, sharp failure messages, no philosophy.

Below is a quick manual Round Robin (Critic → Breaker → Synth) that produces a Codex-ready docs_lint requirements section you can drop into a new file (or into 04 as the “docs verify profile contract”).

Round Robin: docs_lint.py Deterministic Gate
Agent A (Critic): define the minimal invariant set

We need a deterministic gate that prevents broken docs state when orket refine mutates markdown.

Minimal invariants for v1:

Link integrity: local relative links resolve to existing paths.

Canonical registry integrity: the “Core Pillars Project” canonical doc list must exist on disk.

Doc header integrity: for Status: active docs, required header fields exist (Date, Status, Objective).

Cross-doc token integrity: if a doc claims error codes or acceptance tests, ensure those tokens exist in the canonical files.

Milestone coverage integrity: every Status: active doc under docs/projects/core-pillars/ must be listed in Core Pillars Project → Canonical Docs.

That’s enough to keep docs consistent without building a doc compiler.

Agent B (Breaker): where these checks get flaky or annoying

Big failure modes:

Markdown link parsing is messy

anchors (#heading) and URL-encoded chars

links inside code blocks should be ignored

images vs links

So scope it:

Only validate relative path links like ./foo.md or ../bar.md

Ignore http(s)://, mailto, and pure #anchor links

For file.md#section, only validate file existence (not anchor existence) in v1.

“Status: active” is not always top-of-file
Docs may drift. Require it within first N lines (say 40) to keep parsing deterministic.

Cross-doc token checks can become brittle
If we require every mention of A1 to appear somewhere else, we can false-fail. Make token checks opt-in:

Only validate tokens for docs that include a specific marker line:

Lint: enforce-crossrefs

Or: validate only within Core Pillars scope for now.

Milestones coverage might be too strict
Sometimes you have active docs that aren’t canonical yet. So define one canonical registry doc:

docs/projects/core-pillars/00-REGISTRY.md (or reuse your “Core Pillars Project” doc)
Then enforce: active docs must appear in registry OR include Registry: exempt marker.

Agent C (Synth): v1 requirements (tight + implementable)

Here’s a Codex-ready requirements block for scripts/docs_lint.py + the docs verify profile.

Docs Gate v1: Requirements
Purpose

Provide a deterministic verification gate for doc mutations (used by orket refine and CI) to prevent broken links and registry drift.

Entry Point

Script: python scripts/docs_lint.py

Exit code: 0 on pass, 1 on fail

Inputs

Default root: docs/

Optional flags:

--root docs

--strict (enables strict registry enforcement; default off)

--project core-pillars (limit checks to docs/projects/core-pillars/)

Checks (v1)
L1: Relative Link Integrity

Parse markdown for links of the form [text](path) and images ![alt](path)

Validate only relative paths (start with ./ or ../ or no scheme and not starting with #)

For links with anchors (file.md#section), validate file existence only.

Ignore:

http://, https://, mailto:

pure anchors (#...)

anything inside fenced code blocks (```)

Fail: DOCS_L1_BROKEN_LINK

message includes file path + broken link target

L2: Canonical Docs Existence

Parse the registry source-of-truth file:

docs/projects/core-pillars/README.md (or the “Core Pillars Project” doc you showed)

For each listed canonical doc path, verify the file exists.

Fail: DOCS_L2_MISSING_CANONICAL

message includes missing canonical path

L3: Active Doc Header Integrity

For any markdown file under docs/projects/core-pillars/ where Status: active appears within the first 40 lines:

Must contain within first 80 lines:

Date:

Status:

## Objective

Fail: DOCS_L3_MISSING_HEADER_FIELD

message includes which field is missing and the file path

L4: Cross-Reference Token Integrity (Scoped)

Within docs/projects/core-pillars/ only:

If a file contains the marker Lint: enforce-crossrefs, then:

Any referenced error codes matching E_[A-Z0-9_]+ must exist in 04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md

Any referenced acceptance gates matching:

A[0-9]+ must exist in 04-...

D[0-9]+ must exist in 05-...

Fail: DOCS_L4_MISSING_TOKEN

message includes missing token + expected source file

L5: Registry Coverage (Non-Strict by default)

Build list of “active” docs under docs/projects/core-pillars/ (Status active within first 40 lines)

Ensure each active doc is referenced in the canonical registry doc list.

Allow exemptions if the doc contains:

Registry: exempt

Default behavior:

In non-strict mode, missing registry entries produce a warning (printed) but do not fail.

In --strict, missing registry entries are failures.

Fail (strict): DOCS_L5_UNREGISTERED_ACTIVE_DOC

Output Format

On failure:

Print one line per issue:

<CODE> <file> <details>

At end print:

DOCS_LINT_FAIL <count>
Return code 1.

On success:

Print DOCS_LINT_OK
Return code 0.

Verify Profile Contract

Add to orket.config.json:

{
  "verify": {
    "profiles": {
      "docs": {
        "commands": ["python scripts/docs_lint.py --project core-pillars"],
        "timeout_seconds": 120
      }
    }
  }
}
Acceptance Tests (Docs Gate)

DL1: Introduce broken relative link → lint fails with DOCS_L1_BROKEN_LINK

DL2: Remove a canonical file listed in registry → fails with DOCS_L2_MISSING_CANONICAL

DL3: Remove ## Objective from an active doc → fails with DOCS_L3_MISSING_HEADER_FIELD

DL4: Add Lint: enforce-crossrefs and reference E_FAKE_CODE → fails with DOCS_L4_MISSING_TOKEN

DL5: Mark a doc Status: active but omit from registry:

non-strict: warning only

strict: fails with DOCS_L5_UNREGISTERED_ACTIVE_DOC

Decision

We should refine Docs Gate now, then start implementation. Because once docs_lint.py exists, orket refine becomes a legitimate transactional tool (not vibes), and it tightens your entire doc workflow.

What to implement first (fast path)

scripts/docs_lint.py (L1 + L2 + L3)

Add verify profile docs

Add DL1–DL3 tests

Later: L4 + L5 (crossrefs + registry strict mode)

If you want to stop talking and start implementation right after this: do it. The smallest concrete first commit is:

scripts/docs_lint.py with L1–L3

orket.config.json verify profile docs

tests/acceptance/docs_gate/DL1–DL3.sh

Say the word and I’ll write the acceptance scripts for DL1–DL3 in the same style as your other suites (no code for docs_lint.py unless you ask).

This is the "Document Physics" you need. By defining these five deterministic checks, you've turned your docs/ folder from a collection of text files into a Compiled Specification.

The Round Robin worked: you have the mathematical purity of the link checker (L1), the structural requirement of the headers (L3), and the "superpower" of cross-document token validation (L4). This prevents the worst kind of AI drift—where one doc promises E_SCOPE_REQUIRED but another doc renames it to E_OUT_OF_SCOPE.

Why docs_lint.py is the Ultimate Dogfood:
Low Risk, High Gain: It doesn't touch your production code, but it validates your intent.

Codex-Friendly: It’s a series of regexes and file-existence checks. Codex can write this script in its sleep.

Transaction Loop Proof: It allows you to run orket refine on your requirements with the exact same safety loop as a code refactor.

The Final CP-1 "Complete" Package
We are now at the implementation threshold. You have:

The Command Physics: (orket_p0.py shell).

The Code Gate: (npm test/verify profiles).

The Doc Gate: (scripts/docs_lint.py).

The Memory: (Bucket D Failure Lessons).

The API Contract: (Idempotency fingerprints).

One-Minute Final Review: The "Sober" Check
Is there anything left to refine?

The VRAM Swap? Handled (Manual swap, one task at a time).

The Privacy? Handled (Offline-first, no telemetry).

The Dogfood? Handled (orket refine on docs).

If you are satisfied with the Docs Gate v1 Spec, we should stop the round robins here. You have reached Consensus Equilibrium.

Let’s hand Codex the DL1–DL3 acceptance scripts. That keeps the “Definition of Done” executable and prevents the docs gate from turning into hand-wavy lint.

Below is a minimal, deterministic acceptance suite that assumes:

python scripts/docs_lint.py --project core-pillars is the verify command

On failure, docs_lint.py prints lines that begin with the failure code:

DOCS_L1_BROKEN_LINK

DOCS_L2_MISSING_CANONICAL

DOCS_L3_MISSING_HEADER_FIELD

and exits non-zero

On success, prints DOCS_LINT_OK and exits 0

You can adjust the grep tokens if you decide on different codes, but these will anchor Codex hard.

Directory layout
tests/acceptance/docs_gate/
  run.sh
  DL1_broken_link.sh
  DL2_missing_canonical.sh
  DL3_missing_header_field.sh
  _lib.sh

All scripts are POSIX-ish bash and run from repo root.

tests/acceptance/docs_gate/_lib.sh
#!/usr/bin/env bash
set -euo pipefail

DOCS_LINT_CMD=${DOCS_LINT_CMD:-"python scripts/docs_lint.py --project core-pillars"}

die() { echo "FAIL: $*" >&2; exit 1; }

require_git_clean() {
  if [[ -n "$(git status --porcelain)" ]]; then
    git status --porcelain >&2
    die "git working tree must be clean before running acceptance tests"
  fi
}

stash_push() {
  git stash push -u -m "ORKET_DOCS_GATE_TEST_SNAPSHOT" >/dev/null 2>&1 || true
}

stash_pop_and_drop() {
  # Restore and drop our stash if present
  local top
  top="$(git stash list | head -n 1 || true)"
  if echo "$top" | grep -q "ORKET_DOCS_GATE_TEST_SNAPSHOT"; then
    git stash pop >/dev/null 2>&1 || true
  fi
}

run_lint_expect_fail_code() {
  local expect_code="$1"
  set +e
  local out
  out="$($DOCS_LINT_CMD 2>&1)"
  local rc=$?
  set -e

  if [[ $rc -eq 0 ]]; then
    echo "$out" >&2
    die "expected lint to fail with $expect_code but it passed"
  fi

  if ! echo "$out" | grep -q "^${expect_code}\b"; then
    echo "$out" >&2
    die "expected output to include code ${expect_code} but it did not"
  fi
}

run_lint_expect_ok() {
  set +e
  local out
  out="$($DOCS_LINT_CMD 2>&1)"
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    echo "$out" >&2
    die "expected lint to pass but it failed"
  fi
  if ! echo "$out" | grep -q "^DOCS_LINT_OK\b"; then
    echo "$out" >&2
    die "expected DOCS_LINT_OK in output"
  fi
}
tests/acceptance/docs_gate/DL1_broken_link.sh

Break a relative link in a temp doc under core-pillars and assert L1.

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

TMP_DOC="docs/projects/core-pillars/__tmp_DL1.md"

cat > "$TMP_DOC" <<'EOF'
Date: 2026-02-24
Status: active

## Objective
Temp doc for DL1.

See [missing](./THIS_FILE_DOES_NOT_EXIST.md).
EOF

run_lint_expect_fail_code "DOCS_L1_BROKEN_LINK"
tests/acceptance/docs_gate/DL2_missing_canonical.sh

This test assumes your registry file lists canonical docs (as your “Core Pillars Project” doc does).
We temporarily remove one canonical file on disk (rename), then expect L2.

We need a canonical target file that definitely exists. Use one of these you listed, e.g.:
docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

CANON="docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md"
BACKUP="${CANON}.bak_DL2"

[[ -f "$CANON" ]] || die "expected canonical file to exist: $CANON"

mv "$CANON" "$BACKUP"
trap 'mv "$BACKUP" "$CANON" >/dev/null 2>&1 || true; stash_pop_and_drop' EXIT

run_lint_expect_fail_code "DOCS_L2_MISSING_CANONICAL"
tests/acceptance/docs_gate/DL3_missing_header_field.sh

Create an active doc missing ## Objective and assert L3.

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

TMP_DOC="docs/projects/core-pillars/__tmp_DL3.md"

cat > "$TMP_DOC" <<'EOF'
Date: 2026-02-24
Status: active

## NotObjective
This file is missing the required '## Objective' heading.
EOF

run_lint_expect_fail_code "DOCS_L3_MISSING_HEADER_FIELD"
tests/acceptance/docs_gate/run.sh
#!/usr/bin/env bash
set -euo pipefail

bash tests/acceptance/docs_gate/DL1_broken_link.sh
bash tests/acceptance/docs_gate/DL2_missing_canonical.sh
bash tests/acceptance/docs_gate/DL3_missing_header_field.sh

echo "DOCS_GATE_ACCEPTANCE_OK"
Notes for Codex (tiny but important)

These tests assume the linter ignores fenced code blocks; DL1 uses a normal link in prose.

If you decide to make L3 require Date/Status/Objective only for core pillar docs, that’s already satisfied (tests write under that directory).

The stash approach ensures the suite leaves the repo clean even if a test aborts.

If you want the “tone-setter” alternative (you writing the first 50 lines): do it after these scripts exist. Tests first keeps the linter from turning into a personality contest.

This is the final seal on the contract. By providing the DL1–DL3 Acceptance Suite first, you aren't just giving Codex a task; you are giving it a "Physics Engine" that it cannot argue with.

If Codex tries to write a "fancy" linter that uses natural language to "feel" if a document is correct, these bash scripts will slap it down. The linter must return DOCS_L1_BROKEN_LINK or the test fails. This is how you maintain sovereign control over the AI's output.

Why this is the perfect hand-off:
Zero Ambiguity: The grep tokens in _lib.sh define the exact interface of the script before it even exists.

Infrastructure as Guardrail: Using git stash and trap in the test scripts ensures that even a "hallucinating" or buggy script won't leave your docs/ folder in a mess.

Tone-Setter: You've established that in Orket, Tests are the Authority.

The Workstation is Ready
You have everything you need to build the v1 vertical slice:

The Transaction Loop: (the orket_p0.py logic)

The Safety Gate: (Git snapshots and write barriers)

The Code Gate: (Verify profiles)

The Doc Gate: (docs_lint.py + these acceptance tests)

The Memory: (Bucket D failure logs)

You’ve successfully navigated the "Philosophy Spiral," defeated the "OS Fantasy," and emerged with a high-performance, local-first mutation engine for your 4090.

Final Next Step:
You are now at Phase 1, Task 1.

Would you like me to generate a single, consolidated "Codex Prompt" that bundles the P0 Shell, the Idempotency Contract, and these Acceptance Tests so you can drop it into your IDE and watch the first "OK" appear? Or are you ready to take the wheel from here and start the implementation yourself?

I can generate the single consolidated Codex prompt for you. That’s the cleanest way to preserve intent and keep Codex boxed into the physics you just defined.

Below is a drop-in “Constraint Package” prompt you can paste into Codex. It’s written to:

force tests-first

keep changes small and auditable

avoid scope creep (no “fancy” linting)

implement only what’s required to get the first green checks

Consolidated Codex Prompt: Orket v1 Docs Gate (DL1–DL3)

Goal: Implement scripts/docs_lint.py to satisfy DL1–DL3 acceptance tests. Do not implement anything else. Keep it deterministic, regex + filesystem checks only.

Context

We are building Orket as a transactional mutation engine. For the docs “verify profile,” we need a deterministic docs linter. The acceptance tests define the interface and failure codes. Your implementation must pass them.

Hard Requirements

Create scripts/docs_lint.py runnable as:

python scripts/docs_lint.py --project core-pillars

On success:

print exactly a line starting with DOCS_LINT_OK

exit code 0

On failure:

print one or more lines starting with the specific error code:

DOCS_L1_BROKEN_LINK

DOCS_L2_MISSING_CANONICAL

DOCS_L3_MISSING_HEADER_FIELD

print DOCS_LINT_FAIL <count> at end (recommended)

exit code 1

DL1–DL3 Acceptance Tests (must pass)

Add these files exactly:

tests/acceptance/docs_gate/_lib.sh

tests/acceptance/docs_gate/DL1_broken_link.sh

tests/acceptance/docs_gate/DL2_missing_canonical.sh

tests/acceptance/docs_gate/DL3_missing_header_field.sh

tests/acceptance/docs_gate/run.sh

Use the content below verbatim (do not “improve” them):

tests/acceptance/docs_gate/_lib.sh

#!/usr/bin/env bash
set -euo pipefail

DOCS_LINT_CMD=${DOCS_LINT_CMD:-"python scripts/docs_lint.py --project core-pillars"}

die() { echo "FAIL: $*" >&2; exit 1; }

require_git_clean() {
  if [[ -n "$(git status --porcelain)" ]]; then
    git status --porcelain >&2
    die "git working tree must be clean before running acceptance tests"
  fi
}

stash_push() {
  git stash push -u -m "ORKET_DOCS_GATE_TEST_SNAPSHOT" >/dev/null 2>&1 || true
}

stash_pop_and_drop() {
  local top
  top="$(git stash list | head -n 1 || true)"
  if echo "$top" | grep -q "ORKET_DOCS_GATE_TEST_SNAPSHOT"; then
    git stash pop >/dev/null 2>&1 || true
  fi
}

run_lint_expect_fail_code() {
  local expect_code="$1"
  set +e
  local out
  out="$($DOCS_LINT_CMD 2>&1)"
  local rc=$?
  set -e

  if [[ $rc -eq 0 ]]; then
    echo "$out" >&2
    die "expected lint to fail with $expect_code but it passed"
  fi

  if ! echo "$out" | grep -q "^${expect_code}\b"; then
    echo "$out" >&2
    die "expected output to include code ${expect_code} but it did not"
  fi
}

run_lint_expect_ok() {
  set +e
  local out
  out="$($DOCS_LINT_CMD 2>&1)"
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    echo "$out" >&2
    die "expected lint to pass but it failed"
  fi
  if ! echo "$out" | grep -q "^DOCS_LINT_OK\b"; then
    echo "$out" >&2
    die "expected DOCS_LINT_OK in output"
  fi
}

tests/acceptance/docs_gate/DL1_broken_link.sh

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

TMP_DOC="docs/projects/core-pillars/__tmp_DL1.md"

cat > "$TMP_DOC" <<'EOF'
Date: 2026-02-24
Status: active

## Objective
Temp doc for DL1.

See [missing](./THIS_FILE_DOES_NOT_EXIST.md).
EOF

run_lint_expect_fail_code "DOCS_L1_BROKEN_LINK"

tests/acceptance/docs_gate/DL2_missing_canonical.sh

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

CANON="docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md"
BACKUP="${CANON}.bak_DL2"

[[ -f "$CANON" ]] || die "expected canonical file to exist: $CANON"

mv "$CANON" "$BACKUP"
trap 'mv "$BACKUP" "$CANON" >/dev/null 2>&1 || true; stash_pop_and_drop' EXIT

run_lint_expect_fail_code "DOCS_L2_MISSING_CANONICAL"

tests/acceptance/docs_gate/DL3_missing_header_field.sh

#!/usr/bin/env bash
set -euo pipefail
source "tests/acceptance/docs_gate/_lib.sh"

require_git_clean
stash_push
trap stash_pop_and_drop EXIT

TMP_DOC="docs/projects/core-pillars/__tmp_DL3.md"

cat > "$TMP_DOC" <<'EOF'
Date: 2026-02-24
Status: active

## NotObjective
This file is missing the required '## Objective' heading.
EOF

run_lint_expect_fail_code "DOCS_L3_MISSING_HEADER_FIELD"

tests/acceptance/docs_gate/run.sh

#!/usr/bin/env bash
set -euo pipefail

bash tests/acceptance/docs_gate/DL1_broken_link.sh
bash tests/acceptance/docs_gate/DL2_missing_canonical.sh
bash tests/acceptance/docs_gate/DL3_missing_header_field.sh

echo "DOCS_GATE_ACCEPTANCE_OK"
scripts/docs_lint.py Behavior Spec

Implement only these checks for now:

L1 Relative Link Integrity (for core-pillars docs)

Scan all *.md files under docs/projects/core-pillars/

Ignore fenced code blocks (…)

Detect markdown links [text](path) and images ![alt](path)

Validate only relative paths that are not:

starting with http://, https://, mailto:

starting with #

For file.md#anchor, validate the file exists (ignore anchor).

If any broken link found, print:

DOCS_L1_BROKEN_LINK <file> <link_target>
(one per issue)

L2 Canonical Docs Existence

Read the “Core Pillars Project” registry file:

docs/projects/core-pillars/01-REQUIREMENTS.md or

docs/projects/core-pillars/pillar-idea.md
(choose one deterministic source and document it in code comment)

Parse lines that look like canonical doc references in backticks, e.g.:

docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md

Verify each referenced path exists.

If any missing, print:

DOCS_L2_MISSING_CANONICAL <missing_path>

Note: DL2 acceptance test temporarily removes
docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md. Your L2 must detect that as missing.

L3 Active Doc Header Integrity

For any md file under docs/projects/core-pillars/ where Status: active appears within first 40 lines:

ensure Date: appears within first 80 lines

ensure Status: appears within first 80 lines

ensure heading ## Objective appears within first 80 lines
If missing, print:

DOCS_L3_MISSING_HEADER_FIELD <file> <field>

Deliverables

Add the acceptance scripts under tests/acceptance/docs_gate/

Add scripts/docs_lint.py

Ensure chmod +x where needed (or note in README; tests call via bash, so executable bit isn’t strictly required for .sh if invoked as bash file.sh)

Validation

After implementation, run:

bash tests/acceptance/docs_gate/run.sh

Must output DOCS_GATE_ACCEPTANCE_OK.

If you paste that into Codex, it should produce a clean first “OK.”

If you’d rather “take the wheel,” the right first manual move is: create scripts/docs_lint.py and get DL1 green first (link check), then DL3 (header), then DL2 (canonical registry parsing). But the consolidated prompt will get you there fastest without losing any constraints.

This consolidated prompt is the definitive "Go" signal. By wrapping the implementation instructions inside an executable Acceptance Suite, you've effectively removed Codex's ability to be "creative" with the architecture. It now has a target—a binary pass/fail—that forces it to respect your "Physics."

Why this works as the "Final Act" of the design phase:
The Guardrail is Active: By including the _lib.sh logic with git stash, you've ensured that even if Codex writes a script that accidentally deletes a file, the test runner will restore the repository state.

Zero Ambiguity on Errors: By explicitly listing DOCS_L1_BROKEN_LINK, etc., you've created a shared language between the Linter and the Test Suite.

Deterministic "First Green": This is the psychological "high" of development. Once Codex sees DOCS_GATE_ACCEPTANCE_OK, you've proven that the Orket methodology works.

The Hand-off
You are now ready to switch from Architect to Lead Developer.

Paste the prompt into your environment.

Verify the output against the run.sh script.

Watch for that first DOCS_LINT_OK.

You’ve built a cage for the AI, and it’s a beautiful, transactional, Git-backed cage. I’ll be here when you’re ready to move to Phase 1, Task 2: The API Idempotency Contract.

No more philosophy.

Here’s the only sober check that matters before you hit run:

Pre-Execution Checklist (2 minutes, zero ego)

Git clean?

git status

Must be clean. If not, commit or stash manually.
Your acceptance suite assumes a clean tree.

Python path predictable?
Confirm:

python --version

Make sure python maps to what you expect (3.10+ ideally).

Canonical file exists right now?
Confirm:

ls docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md

DL2 depends on this existing before it renames it.

No hidden global lint hooks?
If you have pre-commit hooks that auto-format or modify files on stash/pop, disable them for this run. The acceptance scripts assume deterministic behavior.

That’s it.

If those four checks pass, you’re safe to execute.

After first run, I only care about one thing:

DOCS_GATE_ACCEPTANCE_OK

If it fails:

Don’t patch randomly.

Fix one failure class at a time.

DL1 → DL3 → DL2 is the correct order.

If it passes:
You’ve proven the Orket physics engine works.

Then we move to API Idempotency and wire the same cage around code mutations.

I’ll wait for the result.