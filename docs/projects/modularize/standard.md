# Orket Cross-Layer Reference Standard (Living)

Status: Normative
Package version: `1.0.0-rc4-freeze`
Grand Seal (manifest SHA-256): `ca095ab58519509d22bae0605082e633c4dbc459a9df3b3261c2190ec410c9cc`

## 1) Validation Pipeline (Authoritative)

The validator pipeline is exactly five stages, in this exact order:

`base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`
`base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism` (ASCII)
`base_shape → dto_links → relationship_vocabulary → policy → determinism` (display form)

No additional stage is part of the living contract.

## 2) Canonical JSON Requirements

Canonical bytes are defined as:

1. UTF-8 encoding.
2. LF (`\n`) line endings.
3. Compact JSON separators: `(",", ":")`.
4. `ensure_ascii=False`.
5. `sort_keys=True` (lexicographic order by Unicode code point).
6. Exactly one trailing newline (`\n`).

## 3) Reference Sorting Contract

ReferenceSortKey is:

`(type, id, relationship, namespace, version)`

Missing values are treated as empty strings during sorting.

## 4) Seal Framing Contract

Seal is computed as hash-of-hashes over canonical bytes:

1. Compute canonical bytes for header, body, and links payloads.
2. Compute `header_sha256`, `body_sha256`, and `links_sha256`.
3. Build a frame object containing those three hashes.
4. Canonicalize the frame with the same Canonical JSON rules.
5. Compute `seal_sha256` over those canonical frame bytes.

The hashed bytes are always canonical JSON bytes, never pretty-printed bytes.

## 5) Verification Anchoring Rule

Verifier must recompute header hash using the manifest timestamp value, not the current clock.

Equivalent statement:

`header_hash_input.timestamp = manifest.timestamp`

## 6) CI Enforcement (Required)

1. Triple-Lock: body, links, and manifest must be updated together.
2. No-skip diffing: CI must fail if change-set cannot be determined.
3. Schema drift check: generated schema artifacts must match committed artifacts.

## 7) Package Identity Constants

1. Package version: `1.0.0-rc4-freeze`
2. Grand Seal: `ca095ab58519509d22bae0605082e633c4dbc459a9df3b3261c2190ec410c9cc`

## 8) Scope Boundary

This document intentionally excludes:

1. Full schema JSON blobs.
2. Full manifest JSON body.
3. Conformance examples.
4. Permissive-mode algorithm details.
