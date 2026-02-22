# Orket Modularize Implementation Notes (Living)

Status: Operational guidance for implementers.
Normative pipeline: `base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`.

## 1) Canonical Byte Computation

Use one canonicalizer for all signing and verification inputs:

1. Serialize JSON with `sort_keys=True`.
2. Use compact separators `(",", ":")`.
3. Use `ensure_ascii=False`.
4. Encode UTF-8.
5. Append exactly one trailing newline (`\n`).

This applies to header payload, body payload, links payload, and seal frame payload.

## 2) Hash Computation Flow

Recommended sequence:

1. Build `header_obj` from deterministic inputs.
2. Canonicalize `header_obj` to bytes and hash with SHA-256 -> `header_sha256`.
3. Canonicalize body to bytes and hash -> `body_sha256`.
4. Canonicalize links to bytes and hash -> `links_sha256`.
5. Build `frame_obj = {"header_sha256": ..., "body_sha256": ..., "links_sha256": ...}`.
6. Canonicalize frame bytes and hash -> `seal_sha256`.

Chosen frame shape (authoritative):

```json
{
  "header_sha256": "<hex>",
  "body_sha256": "<hex>",
  "links_sha256": "<hex>"
}
```

Optional HMAC, when enabled:

1. Compute HMAC over canonical frame bytes only.
2. Do not include non-frame bytes in HMAC scope.

## 3) Verification Behavior

Verifier must:

1. Parse manifest.
2. Rebuild header payload using `manifest.timestamp` (never local "now").
3. Recompute `header_sha256`, `body_sha256`, `links_sha256`.
4. Rebuild frame and recompute `seal_sha256`.
5. Compare against manifest values exactly.
6. Fail verification on first mismatch in strict mode.

## 4) CI Verification Scope

CI should decide which DTO triples to verify from changed paths:

1. Detect changed files from VCS diff.
2. Map changes to DTO triplets (`*.body.json`, `*.links.json`, `*.manifest.json`).
3. Enforce Triple-Lock:
   one changed member of a triplet requires all three changed.
4. Verify each affected triplet.
5. Run schema drift check for contract artifacts.

If diff calculation fails, fail closed (No-skip diffing).

## 5) Raw-ID Policy Matching Algorithm (Normative)

Traversal:

1. Recursively traverse the entire DTO JSON value.
2. For each JSON object:
   check every property name, then traverse each value.
3. For each JSON array:
   traverse each element.
4. Scalars:
   no-op.

Match rule:

A property name `p` is a violation if:

1. `p` equals any token in `forbidden_tokens` exactly, OR
2. `p` ends with `"_" + token` for any token in `forbidden_tokens` (underscore-boundary suffix match),
unless `p` is listed verbatim in `allowed_local_ids`.

On violation:

1. Strict:
   emit `E_POLICY_RAW_ID_FORBIDDEN` at stage `policy` and reject.
2. Permissive (if described elsewhere):
   record the error and omit violating fields from semantic processing.

## 6) Drift and Failure Handling

Recommended failure classes:

1. `triplet_incomplete`: body/links/manifest set not fully updated.
2. `manifest_mismatch`: recomputed hash values differ from manifest.
3. `schema_drift`: generated artifact bytes differ from committed artifacts.
4. `pipeline_violation`: stage order differs from the five-stage contract.
5. `determinism_violation`: order-sensitive arrays or manifest rules violated.

Default mode for CI and release gates should be strict/fail-fast.

## 7) Gotchas That Break Determinism

1. Locale-dependent encoding defaults. Always force UTF-8.
2. Windows newline translation. Always write LF.
3. Missing trailing newline in canonical payload.
4. Using pretty-printed JSON for hashing.
5. Using current time instead of manifest timestamp during verify.
6. Non-deterministic key ordering or runtime-dependent map iteration.
7. Inconsistent null handling on the signing path.
   If your implementation strips nulls for links hashing, apply the same rule for verify.

## 8) Practical Guardrails

1. Add golden vectors for canonical bytes and expected hashes.
2. Keep canonicalization logic in one shared function.
3. Keep pipeline stage names as constants to avoid drift.
4. Include deterministic fixtures for both pass and fail cases.

## 9) Legacy Mapping

Note: E_TYPED_REF_MISMATCH is a legacy identifier now enforced within the `dto_links` stage of the 5-stage pipeline.

## 10) Single-Line Log Format (Normative)

All CI/validation events MUST emit one line per event:

`[LEVEL] [STAGE:ci] [CODE:<code>] [LOC:<location>] <message> | <sorted k=v pairs>`

Rules:

1. `LEVEL` is `INFO` or `FAIL`.
2. `location` is RFC 6901 JSON Pointer.
3. Message escapes CR/LF as `\\r` and `\\n`.
4. Detail keys are sorted lexicographically.
5. Bool values render as `true`/`false`.
6. Dict/list values render via:
`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
7. Emit a final summary line:
`[SUMMARY] outcome=PASS|FAIL stage=ci errors=<n> warnings=<n>`.
