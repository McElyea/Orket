# Contract Delta: Governed Compact Turn Packet

## Summary

- Change title: compact governed tool-call turns at the source builder into one minimal system prompt plus one bounded turn packet
- Owner: Orket Core
- Date: 2026-04-04
- Affected contract(s):
  - `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
  - `CURRENT_AUTHORITY.md`
  - `orket/application/workflows/turn_message_builder.py`
  - `orket/runtime/compact_turn_packet.py`
  - `orket/adapters/llm/local_prompting_policy.py`

## Delta

- Current behavior:
  - the Gemma lane already collapsed adjacent `user` blocks to one outbound `user` message, but the merged packet still contained the full legacy system handbook plus a long series of governed contract blocks
  - the source message builder still emitted the old split-prompt stack, so internal `messages.json` artifacts and any upstream provider path could still show `Execution Context JSON`, `Artifact Contract JSON`, `Turn Success Contract`, `Read Path Contract`, `Guard Decision Contract`, and similar blocks
  - even after earlier tool-declaration fixes, the prompt surface still carried far more instruction text and more contradictory sub-prompts than the bounded turn actually required
- Proposed behavior:
  - governed `tool_call` turns now compact at the source builder into one minimal `system` prompt and one bounded `TURN PACKET` `user` prompt
  - the compacted packet preserves only the turn-relevant requirements: required tools, admitted paths, allowed statuses, runtime-verifier outcome, compact guard rules, preloaded read context, corrective instruction, and any required compact evidence sections
  - the old split-prompt block labels no longer survive inside compact packets
  - the Gemma provider lane reuses that shared compact packet and only performs a safety-net collapse if upstream legacy messages still arrive
  - compaction is recorded in provider telemetry through a stable warning token when the provider path had to compact legacy messages
- Why this break is required now:
  - sending the full role handbook plus every verbose contract block to a local model is not a defensible prompting strategy for bounded tool turns
  - the runtime needs a smaller and more coherent prompt surface for Gemma so the model can reliably focus on the actual turn contract instead of a concatenated protocol manual

## Observed Live Evidence

Observed on 2026-04-04:

1. Preconditions before this compaction step:
   - live run `4809bab0` at `.tmp/gemma_guard_fix_live/` had already repaired the guard native-tool declaration seam
   - `002_integrity_guard` still carried the pre-compaction merged governed packet and recorded:
     - `prompt_tokens: 2677`
     - `openai_request_message_count: 2`
     - `openai_request_role_sequence: ["system", "user"]`
   - the old provider packet still corresponded to the verbose governed surface the operator saw in LM Studio logs
2. Postconditions after the provider-facing compaction step:
   - fresh live rerun `2a27e3e5` at `.tmp/gemma_compact_packet_live/` recorded for `002_integrity_guard`:
     - `prompt_tokens: 834`
     - `completion_tokens: 83`
     - `openai_request_message_count: 2`
     - `openai_request_role_sequence: ["system", "user"]`
     - `openai_native_tool_names: ["read_file"]`
     - `openai_tool_choice: "required"`
     - `local_prompting_warnings: ["message_packet_compacted:gemma_tool_turn_v1:11->2"]`
   - the same guard turn still completed truthfully with:
     - `.tmp/gemma_compact_packet_live/observability/2a27e3e5/cwr-01/002_integrity_guard/parsed_tool_calls.json`
     - `.tmp/gemma_compact_packet_live/observability/2a27e3e5/cwr-01/002_integrity_guard/checkpoint.json`
   - `checkpoint.json` for that turn still records `state_delta.from=awaiting_guard_review` and `state_delta.to=done`
3. Source-level structural proof after moving compaction into `turn_message_builder.py`:
   - `.tmp/gemma_source_packet_probe/builder_packet.json` records:
     - `built_message_count: 2`
     - `built_role_sequence: ["system", "user"]`
     - every old split-prompt label probe returns `false`
   - the builder-emitted `user_prompt` now carries one compact `TURN PACKET` with compact headings such as `Runtime Verification` and `Guard Review Rules` instead of the old block labels
4. Fresh live Gemma send status on this machine:
   - `.tmp/gemma_source_packet_probe/runtime_target.json` shows LM Studio currently exposes only `text-embedding-nomic-embed-text-v1.5`
   - requested model `google/gemma-4-26b-a4b` is not installed or loaded in the local LM Studio runtime on 2026-04-04
   - fresh end-to-end live Gemma proof is therefore blocked by local runtime inventory, not by the compact-turn-packet change
5. Net effect:
   - the guard-turn prompt dropped by 1843 prompt tokens on the real LM Studio path while preserving truthful file read plus status closeout
   - the model-facing Gemma prompt is now materially smaller and more coherent without widening tool authority

## Migration Plan

1. Compatibility window:
   - none; the old verbose Gemma provider packet was a failing integration surface, not a desired external contract
2. Migration steps:
   - compact governed `tool_call` turns at the source builder
   - preserve only the bounded turn packet fields that are still needed for tool correctness
   - make the Gemma provider path a compatibility safeguard instead of the primary compaction path
   - record stable compaction telemetry in raw model artifacts when provider-side safeguard compaction occurs
3. Validation gates:
   - focused local-prompting contract tests
   - focused provider request-shape tests
   - focused builder and provider contract tests
   - builder-packet structural proof in `.tmp/gemma_source_packet_probe/builder_packet.json`
   - fresh live Gemma rerun when the local LM Studio runtime again exposes `google/gemma-4-26b-a4b`

## Rollback Plan

1. Rollback trigger:
   - Gemma tool-call completion regresses after compaction or the compacted packet drops required turn constraints
2. Rollback steps:
   - remove the shared compact turn-packet transform from the source builder
   - return to the prior verbose governed packet path
   - keep the previously shipped native tool declaration and parser allowlisting fixes unless they are separately proven harmful
3. Data/state recovery notes:
   - no durable data migration is involved; rollback is code, tests, and docs only

## Versioning Decision

- Version bump type: none at the Orket package level in this working change
- Effective version/date: 2026-04-04 contract change
- Downstream impact:
  - operators can now verify one compact builder packet and one compact provider packet instead of a stack of governed sub-prompts
  - the compacted-packet contract is explicit and versioned through telemetry token `message_packet_compacted:gemma_tool_turn_v1`
