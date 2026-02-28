Phase A/B Sovereign Kernel — Clean, Usable Specification

(Drop-in ready for IMPLEMENTATION_PLAN.md or digest-spec-v1.md)

1. Strategic Impact

Tombstones + typed identity {dto_type, id} transform the kernel from a file-watcher into a deterministic conflict-resolution engine. In local-first systems, hard deletes break convergence; tombstones preserve deletion as evidence so all nodes reach the same conclusion about object existence.

2. Integration Checklist (PR-Ready)
2.1 Registry Lock

contracts/error-codes-v1.json is the authoritative vocabulary.

Kernel MUST enforce:

Every emitted issue.code ∈ registry

Every [CODE:X] token ∈ registry

No dynamic codes, suffixing, or “helpful variants”

Registry MUST contain no duplicates

Registry ordering is stable/deterministic (sorted recommended)

Once digest enforcement is active:

Use specific E_DIGEST_* codes

Do not use E_PROMOTION_FAILED for digest failures

Canonical kernel-law test home:

tests/kernel/v1/

CI gate: python -m pytest -q tests/kernel/v1

2.2 LSI Identity Basis

Universal identity key:

{dto_type}:{id}

Derived from the staged body (never the envelope).

If staged objects are envelope-shaped:

visible_identities = {
    f"{rec['body']['dto_type']}:{rec['body']['id']}"
    for rec in staged_creations
}

Tombstones:

Filename/stem = addressing

Payload {dto_type,id} = identity

Visibility subtraction uses identity keys, not stems

E_TOMBSTONE_STEM_MISMATCH remains the payload.stem vs filename check (identity fields do not replace it)

2.3 TypeScript Parity Harness

Create conformance/ts/.

TS harness validates:

Canonical JSON parity

Digest parity

Against committed golden vectors:

CI consumes vectors; CI never generates them

CI MAY regenerate and diff, but MUST NOT overwrite

2.4 Canonicalization + Digest Law (Phase B v1)

Orket uses a JCS-inspired subset, not strict RFC 8785.

Normative statement:

RFC 8785 is inspiration only; Orket’s canonicalization rules are normative even where they deviate.
Canonical Bytes Rule
canonical_bytes = UTF8(canonical_json_text) + b"\n"

Rules:

Exactly one trailing LF (0x0A)

No CR (\r) anywhere

No extra trailing padding (must NOT end with 0x0A 0x0A)

LF is not JSON syntax; it is part of Orket’s canonical bytes rule

Deterministic precedence:

raw_bytes → UTF-8 validity → physical layout (exactly one LF, no CR, no extra padding)
→ canonicalization → hashing
Logical Canonical JSON Subset

String policy

Literal Unicode (Python ensure_ascii=False)

Escape only: ", \, and control chars (U+0000–U+001F)

Number policy

Integers only (v1)

Range: [-2^53+1, 2^53-1]

Out-of-range or non-integer → E_DETERMINISM_INVALID_NUMBER

-0 MUST canonicalize as 0

Object policy

Keys MUST be sorted by their UTF-8 encoded byte sequence (ascending)

No whitespace

Array policy

Canonicalize each element recursively

Digest Computation (v1)

Algorithm identifier: "sha256" (lowercase)

Digest is computed over canonical_bytes

Digest failure mapping:

Canon mismatch / canonicalization deviation → E_DIGEST_NON_CANONICAL_JSON

Missing trailing LF → E_DIGEST_TRAILING_NEWLINE_REQUIRED

CR present, double-LF, or padding drift → E_DIGEST_NORMALIZATION_MISMATCH

Invalid UTF-8 (byte gate) → E_DIGEST_INVALID_UTF8

Algorithm mismatch → E_DIGEST_ALGORITHM_MISMATCH

Digest length mismatch → E_DIGEST_LENGTH_MISMATCH

Hex formatting violation → E_DIGEST_HEX_INVALID

Digest mismatch → E_DIGEST_VALUE_MISMATCH

3. Registry Guardrail Test (Drop-In)

File: tests/kernel/v1/test_registry.py

Purpose: enforce registry governance mechanically.

Test requirements:

Load registry

Validate: pattern compliance + no duplicates

Collect emitted codes from:

issue.code

[CODE:X] tokens

Assert all emitted codes ∈ registry

Deterministic failure message, e.g.:

Violation: Code 'E_SOME_NEW_THING' is not registered in contracts/error-codes-v1.json.
4. Golden Vectors (The “Vector Handshake”)

Golden vectors enforce cross-language determinism (Python ↔ TS).

Rules:

Maintainer-only: Python script generates vectors locally

Vectors are committed

CI consumes committed vectors only

CI MAY regenerate and diff, but MUST NOT overwrite

Vector file:

tests/kernel/v1/vectors/digest-v1.json

Top-level MUST include:

version: "digest-v1"

algorithm: "sha256"

vectors: [...]

Vector types:

A) Object vectors

{
  "name": "...",
  "input": {...},
  "canonical": "...",
  "digest_hex": "..."
}

B) Raw-bytes vectors (byte gate)

{
  "name": "...",
  "raw_utf8": "...",
  "expect_error": "E_DIGEST_*"
}

Invalid UTF-8 requires raw bytes encoding:

{
  "name": "fail-invalid-utf8-lone-continuation",
  "raw_b64": "gA==",
  "expect_error": "E_DIGEST_INVALID_UTF8"
}

Recommended “evil vectors” (drift catchers):

Deep nesting

Mixed arrays + objects

Unicode literal vs escaped representation

Empty structures

JS safe integer boundary

5. Identity Wall Intent

Stage builds {dto_type}:{id} from staged bodies.

LSI validates links against:

Committed visible set

Staged creations

Promotion only writes when:

No orphans

No invalid tombstones

No registry violations

6. Registry Auditor (Truth Triangle)

File: scripts/audit_registry.py

Purpose: keep registry synchronized with the normative spec so developers don’t have to “read code” to learn meanings.

Rules enforced:

Every code in registry MUST appear in docs/KERNEL_REQUIREMENTS_EXIT.md

Every code mentioned in docs/KERNEL_REQUIREMENTS_EXIT.md MUST be in registry

Registry sorted + no duplicates

Diff-style failure output (add/remove guidance)

7. Final Execution Gate

Maintainer-only:

python scripts/gen_digest_vectors.py (regenerate vectors; commit + review)

Local/CI verification (Gitea workflows / local runners):

python scripts/audit_registry.py (registry ↔ spec sync)

python -m pytest -q tests/kernel/v1 (kernel + governance)

npm test --prefix conformance/ts (cross-language parity)

Failure conditions:

Any drift in canonical string or digest_hex → fail

Any unregistered emitted code/token → fail

Any registry↔spec mismatch → fail

If you want one more tightening pass, the next “nice to have” is a tiny glossary block that defines: raw_bytes, canonical_json_text, canonical_bytes, and visible_identities in 4 bullet points—useful for future contributors.

0) One spec fix: declared digest path + error mapping

Lock this:

Declared digest location: envelope.digest

envelope.digest.algorithm = "sha256" (fixed)

envelope.digest.hex = 64-char lowercase hex

Reason: envelope.digest.sha256 as a property name is fine, but then you still need to validate presence and format, and it tends to invite “multiple algos as keys” later. algorithm + hex is simpler and more future-proof.

Deterministic error precedence (recommended)

Missing envelope.digest or missing required fields → E_DIGEST_NON_CANONICAL_JSON (it’s a semantic/canonicalization violation for your envelope contract)

Algorithm not "sha256" → E_DIGEST_ALGORITHM_MISMATCH

Hex not lowercase 64-hex → E_DIGEST_HEX_INVALID

Hex length not 64 → E_DIGEST_LENGTH_MISMATCH (optional; you can fold into HEX_INVALID if you prefer fewer branches)

If you really want to keep your earlier mapping “failure to parse path → HEX_INVALID / ALGORITHM_MISMATCH”, you can—just make sure it’s deterministic and tested in vectors. The key is: missing path must not sometimes become NON_CANONICAL_JSON and sometimes HEX_INVALID depending on code path.

1) What Gitea experiments I want you to run

These are tiny, reversible, and they verify the whole chain without you needing GitHub Actions.

Experiment A — Prove the “Truth Triangle” gates work

Goal: A PR cannot merge if it breaks:

registry ↔ spec sync (scripts/audit_registry.py)

python kernel gate (pytest tests/kernel/v1)

TS parity (npm test --prefix conformance/ts)

and importantly: vectors are not regenerated/overwritten

Do this in Gitea:

Create a branch exp/audit-triangle.

Make a trivial change that should fail audit:

add a fake code string like E_FAKE_TEST_CODE only to contracts/error-codes-v1.json and commit.

Open a PR into main.

Confirm the runner reports:

audit fails with a diff section showing it’s missing in spec.

Then fix it by adding the code to the spec (docs file) and re-run:

now audit passes, but registry guardrail still needs to pass.

Finally remove the fake code from both places and confirm green again.

Why this matters: It validates your registry is authoritative but synchronized, and that drift is caught at PR time.

Experiment B — Prove “Golden vectors are golden” (CI consumes, never rewrites)

Goal: Your runner must fail if generator output differs from committed vectors, but must not overwrite them.

Do this:

Create branch exp/vector-golden.

Intentionally break committed vectors:

change one digest_hex in tests/kernel/v1/vectors/digest-v1.json by one character.

PR should fail in Python vector consumer test and/or TS parity.

Now revert that change and instead modify the generator (e.g., reorder keys intentionally) so it would generate different output.

Runner should fail on the “regen+diff” step (if you include it), and you should confirm no files were rewritten by the runner.

Minimal runner check to add (if not already):

python scripts/gen_digest_vectors.py --out /tmp/digest-v1.json
diff -u tests/kernel/v1/vectors/digest-v1.json /tmp/digest-v1.json
Experiment C — Prove “One law per PR” is enforceable socially + mechanically

Goal: Make PRs small and verifiable.

Do this:

Create two PRs that each change one “law”, and verify your checks and review UI are pleasant:

PR that only touches registry + guardrail test

PR that only touches base_shape validation + tests

This is mostly a human ergonomics check: are reviewers getting clean diffs, do checks attach nicely, etc.

2) Gitea runner/pipeline setup (what to configure)

If you tell me which runner you’re using, I’ll tailor the config:

Gitea Actions (GitHub Actions-like YAML but runs locally)

Drone

Woodpecker

Jenkins

Act Runner (Gitea’s runner)

If you’re on Gitea Actions, your single job should run:

python scripts/audit_registry.py
python -m pytest -q tests/kernel/v1
npm test --prefix conformance/ts

Plus optional “vector regen diff” check (recommended) after python install and before tests.

3) Confirming your Phase B start vectors

These two are perfect “first handshake” acceptance vectors for PR-B1:

Invalid UTF-8 poison pill:

{"raw_b64":"gA==","expect_error":"E_DIGEST_INVALID_UTF8"}

Missing newline:

{"raw_utf8":"{\"a\":1}","expect_error":"E_DIGEST_TRAILING_NEWLINE_REQUIRED"}

I’d add one more Byte Gate negative immediately because it catches Windows drift early:

{"raw_utf8":"{\"a\":1}\r\n","expect_error":"E_DIGEST_NORMALIZATION_MISMATCH"}
4) What I need from you to tailor the runner config exactly

Reply with just these three items (no extra ceremony):

Which workflow runner you’re using with Gitea (Actions/Drone/Woodpecker/etc.)

Your repo’s language toolchain install assumptions on the runner (python version? node already installed?)

Whether you want PRs blocked on:

required checks (hard block) or

advisory checks (soft)

And if you paste your current “turn result” JSON shape (even a minimal stub), I’ll also lock the guardrail test to your exact issues[] / events[] paths with zero guesswork.