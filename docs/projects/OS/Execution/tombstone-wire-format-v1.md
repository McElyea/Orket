# Tombstone Wire Format (v1)

Status: Normative
Version: `kernel_api/v1`

## Purpose
Define a deterministic wire format for delete operations so deletion behavior is stable across implementations and replay.

## File Discovery
1. Tombstone filename MUST be `<stem>.tombstone.json`.
2. Tombstones MAY exist under nested staged paths.
3. Filename-implied stem MUST match payload `stem`.

## Payload (strict)
```json
{
  "kind": "tombstone",
  "stem": "path/to/stem",
  "deleted_by_turn_id": "turn-0001"
}
```

Rules:
1. `kind` MUST equal `"tombstone"`.
2. `stem` MUST be non-empty and normalized to forward-slash path form.
3. `deleted_by_turn_id` MUST be non-empty and match current promotion turn.
4. Additional properties are not allowed.

## Visibility Rule
For LSI target resolution, a stem is visible only if it exists in sovereign index and does not have a corresponding staged tombstone, unless that stem is re-created in the same turn.

## Required Errors
1. `E_TOMBSTONE_INVALID`
2. `E_TOMBSTONE_STEM_MISMATCH`
3. `E_DELETE_MISSING_TOMBSTONE` (if delete is requested without tombstone evidence)

## Behavior Vectors (Normative)
1. Deletion-only promotion:
staging contains only tombstones -> promotion PASS, deleted stems become not visible.
2. Missing/empty staging with no tombstones:
promotion PASS as no-op, turn sequence still advances.
3. Tombstone + recreate in same turn:
recreate wins for post-promotion visibility.

## Reference Vectors
Canonical digest vectors for tombstone payloads are maintained in test fixtures and validated in CI.
