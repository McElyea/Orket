# Truthful Runtime Repair Ledger Contract

Last updated: 2026-03-16
Status: Active
Owner: Orket Core
Canonical packet authority: `docs/projects/archive/truthful-runtime/TRH03162026-PHASE-C-CLOSEOUT/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-PACKET2-IMPLEMENTATION-PLAN.md`
Related authority:
1. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
2. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`

## Purpose

Define the durable packet-2 runtime-owned repair-history contract extracted from the reopened bounded Phase C packet-2 slice.

This contract governs the minimum runtime truth surfaces for:
1. structured repair history
2. repair reason and strategy attribution
3. final repair disposition
4. deterministic reconstruction of emitted repair-ledger facts

## Scope

In scope:
1. additive `run_summary.json` extension contract for packet-2 repair history
2. repair-ledger entry shape and stable field semantics
3. ledger-recorded packet-2 reconstruction requirements
4. currently proven corrective-reprompt repair source mapping

Out of scope:
1. narration-to-effect audit beyond repair-entry attribution
2. retries or writes idempotency policy beyond repair-ledger needs
3. source attribution and evidence-first mode
4. voice truth and artifact-generation provenance
5. Phase D memory and trust-policy work
6. Phase E promotion and governance work

## Canonical Surface

1. Packet 2 uses one canonical runtime-owned storage surface: a `run_summary.json` additive extension.
2. Packet-2 repair-ledger additions must live under the `truthful_runtime_packet2` extension object and must not break readers that ignore unknown fields.
3. Minimum packet-2 extension shape is:
   1. `schema_version`
   2. `repair_ledger`
4. `repair_ledger` must include:
   1. `repair_occurred`
   2. `repair_count`
   3. `final_disposition`
   4. `entries`
5. Packet-2 repair-ledger fields are omitted rather than set to `null`.
6. The `truthful_runtime_packet2` extension is omitted when no runtime-owned repair entries exist for the finalized run.

## Repair Ledger Contract

1. `repair_occurred` must be `true` whenever the packet-2 extension is emitted.
2. `repair_count` must equal `len(entries)`.
3. `final_disposition` must be one of:
   1. `accepted_with_repair`
   2. `no_repair`
4. Each repair-ledger entry must include:
   1. `repair_id`
   2. `turn_index`
   3. `source_event`
   4. `strategy`
   5. `reasons`
   6. `material_change`
5. `issue_id` is optional and is omitted when no stable issue identifier exists for the repair entry.
6. `repair_id` must be a stable identifier for the repair event rather than a free-form message.
7. `reasons` must be unique, deterministically ordered stable reason codes.
8. `source_event` must name the canonical runtime event that caused the repair entry.
9. `strategy` must name the canonical runtime repair strategy rather than operator prose.
10. `material_change` must be `true` only when validator-driven repair materially changed the accepted final output.

## Reconstruction Rule

1. Packet 2 must remain compatible with the `run_summary.json` authority in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`.
2. All facts required to reconstruct the packet-2 repair ledger must be recorded in ledger state before final summary generation completes.
3. Packet-2 reconstruction must never require artifact byte inspection, prompt inspection, or log parsing as the canonical replay path.
4. The authoritative replay source for packet-2 reconstruction is the ledger-recorded `packet2_fact` event payload.
5. Packet-2 reconstruction must satisfy:
   1. `reconstructed packet-2 extension == emitted packet-2 extension`

## Corrective-Reprompt Mapping

1. The currently proven packet-2 repair source event is `turn_corrective_reprompt`.
2. When a repair entry is derived from corrective reprompt behavior:
   1. `source_event` must be `turn_corrective_reprompt`
   2. `strategy` must be `corrective_reprompt`
3. When stable contract-reason codes are available at the corrective-reprompt boundary, `reasons` must be derived from those stable codes.
4. Packet 2 is additive to packet 1:
   1. packet 2 records repair history and disposition
   2. packet 1 continues to own the final truth classification and defect/conformance surfaces

## Emission Boundary

1. Packet-2 repair-ledger emission must not change terminal run status.
2. Packet-2 repair-ledger emission must not weaken packet-1 conformance or classification semantics.
3. If packet 2 is absent, consumers must not infer that repair history is `no_repair`; absence means no emitted packet-2 repair-ledger surface for that run.
