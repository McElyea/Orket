# Card Prompt Truth and Explicit JSON Object Requests

## Summary
- Change title: Align card prompt sections and verifier claims with execution.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and
  `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md` under `docs/specs/`.

## Delta
- Opening behavior: compact extraction copied the complete system-prompt tail
  into project/patch sections, repeating later acceptance. Prompts advertised a
  legacy verifier even when disabled, and an inferred no-argument app command
  even when an explicit command replaced it. The selected llama.cpp host returned
  fenced output despite a bare JSON-object request.
- Required behavior: preserve each named section body once. Application context
  carries the resolved verifier-enable flag; both prompt formats share the pure
  selection rule and omit disabled commands. Explicit commands replace inferred
  app commands. Declared acceptance remains independent of this legacy setting.
- Canonical summation stages declare their real output/review paths. Requirements,
  design and optional attribution use artifact profiles; implementation and review
  use the app profile. The deterministic provider no longer writes a placeholder
  Python file during requirements. Disabled legacy verification removes only the
  inferred support-artifact read; explicit turn-contract reads are retained.
- The explicit `json_object` override now includes `schema: {type: object}` for
  llama.cpp. This is the provider's documented encoding for the same requested
  JSON-object constraint. Other providers retain their request form; an unset
  override does not opt into JSON mode. The selected host, model and profile stay
  unchanged. There is no response cleanup, parser relaxation, alternate provider
  or inference retry added by this change.
- Reason: prompts must not invent execution requirements or duplicate authority;
  a structured-output request must have observed enforcement on the selected host.

## Migration Plan
1. No persistent schema or retained evidence migration. New prompts and request
   fingerprints reflect the actual composed inputs; historical artifacts remain.
2. Standard orchestration supplies the resolved boolean explicitly. Direct
   prompt callers that omit it retain their existing enabled default.
3. Gates: settings precedence and both formats, exact section preservation with
   real persisted acceptance, provider request-shape contracts, and real canonical
   workload execution through llama.cpp. A formatting-only probe is not workload
   completion or general provider conformance.

## Rollback Plan
1. Trigger: lost prompt content, changed acceptance semantics, rejected provider
   request forms, or incorrect verifier selection.
2. Repair or restore the affected renderer/request encoder while retaining the
   failure evidence. Do not accept malformed output to produce a green proof.
3. No production state or historical proof is rewritten by this checkpoint.

## Versioning Decision
- No release, commit or version bump is performed in this checkpoint.
- Effective date: 2026-09-12. Existing packet/envelope and evidence schemas remain.
- Prompt/request fingerprints change. Provider JSON support remains conditional
  on observed server behavior; no broader workload capability is admitted.
