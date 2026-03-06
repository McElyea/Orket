# Protocol Ledger Parity Campaign Schema (v1)

Last updated: 2026-03-06  
Status: Active (schema contract)  
Owner: Orket Core

This document defines the stable output contract for ledger parity campaign artifacts emitted by:

1. `orket/runtime/protocol_ledger_parity_campaign.py`
2. `scripts/protocol/run_protocol_ledger_parity_campaign.py`
3. `GET /v1/protocol/ledger-parity/campaign`
4. `orket protocol parity-campaign`

## Top-Level Fields

Required:
1. `sqlite_db` (string path)
2. `protocol_root` (string path)
3. `candidate_count` (integer)
4. `parity_ok_count` (integer)
5. `mismatch_count` (integer)
6. `all_match` (boolean)
7. `digest_mismatch_count` (integer)
8. `rows` (array)
9. `mismatches` (array)
10. `compatibility_telemetry_delta` (object)

Optional discovery context:
1. `requested_session_ids` (array[string])
2. `discovered_sqlite_session_ids` (array[string])
3. `discovered_protocol_session_ids` (array[string])

## Row Shape

Each row in `rows` and `mismatches` contains:

1. `session_id` (string)
2. `parity_ok` (boolean)
3. `difference_count` (integer)
4. `difference_fields` (array[string])
5. `sqlite_digest` (string|null)
6. `protocol_digest` (string|null)
7. `sqlite_status` (string)
8. `protocol_status` (string)

## Compatibility Telemetry Delta

`compatibility_telemetry_delta` includes:

1. `field_delta_counts`  
   key: differing field name, value: mismatch count
2. `delta_signature_counts`  
   key: `<field>:<sqlite_value>-><protocol_value>`, value: count
3. `status_delta_counts`  
   key: `status:<sqlite_status>-><protocol_status>`, value: count

## Strict Gate Guidance

1. CI strict mode should fail when `mismatch_count > 0` unless an explicit temporary threshold is approved.
2. Operator rollout bundles should store both:
   - this parity campaign payload
   - replay campaign payload from `replay-campaign-schema.md`
