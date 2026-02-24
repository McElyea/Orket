# Canonicalization Rules (v1.2)

Last updated: 2026-02-24
Status: Normative for v1.2 execution

## Canonical JSON Rules
1. UTF-8 encoding only.
2. `ensure_ascii = false`.
3. Object keys sorted by Unicode codepoint.
4. Separators are `,` and `:` with no trailing whitespace.
5. No trailing data before/after the JSON payload.
6. No Unicode normalization transforms (preserve original codepoints).
7. Canonical bytes are hashed directly; no host-specific line-ending conversion.

## Numeric Rules
1. Floats are forbidden on canonical surfaces.
2. NaN, Infinity, and `-0` are forbidden.
3. Fractional quantities must be string-encoded or fixed-point integers.

## Failure Rule
1. Canonicalization rule violations fail closed with `E_CANONICALIZATION_ERROR`.
