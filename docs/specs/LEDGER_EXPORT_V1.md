# Ledger Export v1

Last updated: 2026-04-26

Status: Active contract for the NorthstarRefocus outward-facing pipeline Phase 4.

## Purpose

`ledger_export.v1` defines the operator-visible run ledger export and offline verification contract for the outward-facing pipeline.

The canonical operator loop is:

```text
submit -> review -> decide -> inspect -> export -> verify
```

This contract covers only outward-facing `run_events` produced by the v1 pipeline. Legacy run artifacts are not silently promoted into canonical ledger events.

## Ledger Payload Model

For v1, `run_events.payload` is the canonical outward-facing event payload and must already be policy-safe by construction.

Raw sensitive tool inputs, provider payloads, or internal artifacts must not be stored in `run_events.payload` unless an explicit run policy allows PII-bearing ledger payloads and the resulting export is marked as including PII.

Offline verification recomputes hashes from exported event payloads. Therefore, any export that redacts, omits, or transforms already-recorded event payload bytes is a `partial_view`, not the same full canonical ledger.

## Canonical Event Hashing

Canonical event order for a run is ascending:

```text
(run_id, turn, at, event_id)
```

The first event uses:

```text
previous_chain_hash = "GENESIS"
```

`event_hash` is SHA-256 over the UTF-8 bytes of canonical JSON with sorted keys and compact separators for exactly this object:

```json
{
  "event_id": "...",
  "event_type": "...",
  "run_id": "...",
  "turn": 1,
  "agent_id": "...",
  "at": "...",
  "payload": {}
}
```

The hash input excludes `event_hash`, `chain_hash`, `previous_chain_hash`, `position`, `event_group`, and export-only metadata.

`chain_hash` is SHA-256 over the UTF-8 bytes of:

```text
previous_chain_hash + "\n" + event_hash
```

`ledger_hash` is the final canonical `chain_hash`. An empty ledger has `ledger_hash = "GENESIS"`, but outward-facing exports for known runs normally include at least the `run_submitted` event.

## Event Groups

The `types` filter uses event groups, not arbitrary event type prefixes.

| Group | Included event types |
|---|---|
| `proposals` | `proposal_made`, `proposal_pending_approval` |
| `decisions` | `proposal_approved`, `proposal_denied`, `proposal_expired`, `proposal_policy_rejected` |
| `commitments` | `commitment_recorded` |
| `tools` | `tool_invoked` |
| `audit` | `ledger_export_requested` |
| `all` | all v1 outward ledger events |

`ledger_export_requested` belongs to `audit`. It is included in `all` exports and excluded from `proposals`, `decisions`, `commitments`, and `tools` filtered exports unless `audit` is also requested.

## Full Canonical Export

A full canonical export has:

```json
{
  "schema_version": "ledger_export.v1",
  "export_scope": "all",
  "run_id": "...",
  "types": ["all"],
  "include_pii": false,
  "contains_pii": false,
  "summary": {},
  "policy_snapshot": {
    "ledger_payload_model": "policy_safe_by_construction",
    "payload_bytes": "unchanged",
    "outbound_policy_gate": "applied_before_serialization"
  },
  "canonical": {
    "ordering": ["run_id", "turn", "at", "event_id"],
    "genesis": "GENESIS",
    "event_count": 0,
    "ledger_hash": "GENESIS"
  },
  "events": [],
  "omitted_spans": [],
  "verification": {
    "result": "valid",
    "meaning": "full canonical ledger"
  }
}
```

Each event object includes:

```json
{
  "position": 1,
  "event_group": "proposals",
  "previous_chain_hash": "GENESIS",
  "event_id": "...",
  "event_type": "...",
  "run_id": "...",
  "turn": 1,
  "agent_id": "...",
  "at": "...",
  "payload": {},
  "event_hash": "...",
  "chain_hash": "..."
}
```

For a full canonical export, exported event payloads must be byte-equivalent to the canonical JSON hash inputs derived from `run_events.payload`.

## Partial Verified View

A filtered or redacted export is a partial verified view:

```json
{
  "schema_version": "ledger_export.v1",
  "export_scope": "partial_view",
  "types": ["proposals", "decisions"],
  "canonical": {
    "event_count": 10,
    "ledger_hash": "..."
  },
  "events": [],
  "omitted_spans": []
}
```

Partial views must:

1. include canonical `ledger_hash`,
2. include canonical `position` for every disclosed event,
3. include `previous_chain_hash` for every disclosed event,
4. include omitted span anchors,
5. verify disclosed event hashes and disclosed chain links,
6. avoid claiming full-ledger completeness or omitted payload verification.

An omitted span object has:

```json
{
  "from_position": 2,
  "to_position": 4,
  "previous_chain_hash": "...",
  "next_chain_hash": "..."
}
```

`previous_chain_hash` is the chain hash immediately before the omitted span, or `GENESIS` when the span begins at position 1. `next_chain_hash` is the chain hash at the end of the omitted span. These anchors preserve the canonical chain commitment without disclosing omitted event payloads.

## Export Audit Event

When an export with `include_pii: true` is requested through a running Orket instance, the runtime must append a `ledger_export_requested` event before serializing the export response.

Payload:

```json
{
  "run_id": "...",
  "operator_ref": "...",
  "include_pii": true,
  "export_scope": "all",
  "types": ["all"],
  "requested_at": "..."
}
```

The event group is `audit`.

## Verification Results

Verification result vocabulary:

| Result | Meaning |
|---|---|
| `valid` | A full canonical export recomputed successfully from exported payloads. |
| `partial_valid` | A partial view recomputed successfully for disclosed events and anchors, without claiming omitted payload verification. |
| `invalid` | Hashes, ordering, schema, anchors, or required fields failed verification. |

Verification must return diagnostics for invalid exports and must not treat structural parsing success as ledger verification.
