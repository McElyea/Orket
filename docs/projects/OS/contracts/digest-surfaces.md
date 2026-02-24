# Digest Surfaces (v1.2)

Last updated: 2026-02-24
Status: Normative for v1.2 execution

## TurnResult Digest Surface
`turn_result_digest` is computed from a normalized TurnResult projection that includes contract surfaces and excludes diagnostics.

Included:
1. Contract/version fields.
2. Transition evidence digests and structural fields.
3. Capability decision parity surfaces.
4. Normalized issues with `message` nullified.

Excluded:
1. `events`.
2. `KernelIssue.message`.
3. Other declared diagnostic-only fields.

## Report ID Surface
`report_id` uses canonical replay report bytes with:
1. `report_id = null`
2. `mismatches[*].diagnostic = null`

## Nullification Rule
1. Excluded hash fields must be nullified, not removed.
2. Key presence is part of cross-runtime shape stability.
