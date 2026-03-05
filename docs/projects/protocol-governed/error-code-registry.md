# Protocol Error Code Registry (v1)

Last updated: 2026-03-04  
Status: Draft  
Owner: Orket Core

Runtime source of truth:
1. `orket/runtime/protocol_error_codes.py`

This registry defines stable protocol-governed error codes and prefixes used by:
1. parser and validator boundaries
2. ledger framing and replay
3. receipt materialization and replay projections
4. lease and commit race semantics
5. deterministic runtime control surfaces

## Usage Rules

1. Error codes are uppercase tokens prefixed with `E_`.
2. Detail suffixes use `:` separators (for example `E_LEDGER_CORRUPT:offset=128`).
3. Exact codes represent terminal classes.
4. Prefix codes represent parameterized families.
5. New codes require registry updates and test coverage.

## Exact Codes

| Code | Description |
|---|---|
| `E_PARSE_JSON` | Strict response parser failed canonical JSON boundary checks. |
| `E_LEDGER_RECORD_TOO_LARGE` | LPJ-C32 payload exceeded max ledger record bytes. |
| `E_LEDGER_CORRUPT` | CRC32C mismatch for a fully addressable ledger record. |
| `E_LEDGER_SEQ` | Missing, duplicate, or non-monotonic `event_seq`. |
| `E_LEDGER_PARSE` | Ledger payload bytes failed strict JSON-object parsing. |
| `E_LEASE_EXPIRED` | Worker lease expired or renewal compare-and-swap failed. |
| `E_DUPLICATE_OPERATION` | First-commit-wins conflict on `operation_id`. |

## Prefix Codes

| Prefix | Description | Example |
|---|---|---|
| `E_WORKSPACE_CONSTRAINT` | Path safety violation in runtime validator pipeline. | `E_WORKSPACE_CONSTRAINT:path_traversal` |
| `E_RECEIPT_SEQ_INVALID` | Receipt sequence value not parseable or invalid. | `E_RECEIPT_SEQ_INVALID:abc` |
| `E_RECEIPT_SEQ_NON_MONOTONIC` | Receipt sequence not strictly increasing. | `E_RECEIPT_SEQ_NON_MONOTONIC:1<=last:1` |
| `E_RECEIPT_LOG_PARSE` | Receipt log line failed JSON parse. | `E_RECEIPT_LOG_PARSE:line=7` |
| `E_RECEIPT_LOG_SCHEMA` | Receipt log line was not a JSON object. | `E_RECEIPT_LOG_SCHEMA:line=9` |
| `E_NETWORK_MODE_INVALID` | Unsupported deterministic network mode input. | `E_NETWORK_MODE_INVALID:internet` |

## Compatibility Contract

1. Existing codes must not be repurposed.
2. Existing code meanings must remain backward compatible.
3. Prefix contracts must keep their semantic family.
4. New codes are additive unless protocol version increments.

## Operational Guidance

1. Logs should include full `<code>:<detail>` when detail exists.
2. Dashboards should aggregate by:
   - exact code when present
   - prefix family for parameterized errors
3. Retry logic should key on code family, not free-form message text.

## Validation Checklist

1. `is_registered_protocol_error_code(value)` returns `true` for all emitted runtime errors.
2. Any new emitted code is added to registry tests.
3. Error family usage in parser/ledger/replay paths remains deterministic.
