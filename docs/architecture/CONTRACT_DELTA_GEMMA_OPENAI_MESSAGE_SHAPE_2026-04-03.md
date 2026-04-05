# Contract Delta: Gemma OpenAI Message Shape

## Summary

- Change title: collapse adjacent Gemma user prompt blocks before LM Studio submission
- Owner: Orket Core
- Date: 2026-04-03
- Affected contract(s):
  - `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
  - `orket/adapters/llm/local_prompting_policy.py`
  - `orket/adapters/llm/local_model_provider.py`

## Delta

- Current behavior:
  - one logical governed turn was assembled as one `system` message plus many adjacent `user` messages
  - LM Studio received the Gemma 4 guard turn in that fragmented shape, for example one `system` block followed by eleven `user` blocks in the observed pre-change payload
  - first-write success was already possible on `CWR-01` turn `001_coder`, but the guard turn still consumed budget on free-form reasoning instead of native tool calls
- Proposed behavior:
  - the Gemma 4 OpenAI-compatible profile collapses adjacent `user` blocks into one merged `user` turn before provider submission
  - the native `system` role remains intact
  - model raw artifacts now record `openai_request_message_count`, `openai_request_role_sequence`, and `openai_request_role_counts` so outbound request shape is observable without relying on external server logs
- Why this break is required now:
  - Gemma 4 guidance uses standard `system` + `user` chat turns and native function calling rather than fragmented same-role prompt stacks
  - the fragmented LM Studio payload was a runtime-internal layering artifact, not a model-native contract
  - the narrower canonical shape is easier to verify and reduces false confidence about what the provider actually received

## Observed Live Evidence

Observed on 2026-04-03:

1. Precondition before the change:
   - live run `46fbf4e4` reached first file write on `CWR-01` turn `001_coder`
   - the user-observed LM Studio guard payload for that same run showed one `system` block followed by many adjacent `user` blocks
2. Postcondition after the change:
   - fresh live rerun `a13f797e` at `.tmp/gemma_probe_live5/` still wrote `.tmp/gemma_probe_live5/agent_output/requirements.txt`
   - turn `001_coder` raw telemetry records `openai_request_message_count: 2` and `openai_request_role_sequence: ["system", "user"]`
   - turn `002_integrity_guard` raw telemetry also records `openai_request_message_count: 2` and `openai_request_role_sequence: ["system", "user"]`
   - turns to first file write remain `1`
3. Remaining blocker after the change:
   - `002_integrity_guard` still returned length-capped reasoning text with no tool calls, so the overall epic run remained blocked after the first write

## Migration Plan

1. Compatibility window:
   - no compatibility window is needed for Gemma 4 on the LM Studio/OpenAI-compatible lane because the prior fragmented request shape was not the intended external contract
2. Migration steps:
   - normalize adjacent Gemma `user` blocks inside local prompting policy before provider submission
   - expose outbound request-shape telemetry in model raw artifacts
   - update the local prompting spec so the admitted Gemma lane matches runtime behavior
3. Validation gates:
   - targeted prompt-policy and provider payload tests
   - fresh live rerun of `python main.py --epic challenge_workflow_runtime --workspace .tmp/gemma_probe_live5 --build-id gemma_probe_live5 --model google/gemma-4-26b-a4b`

## Rollback Plan

1. Rollback trigger:
   - live Gemma runs regress on first-write success or prove that the collapsed request shape performs worse than the fragmented shape
2. Rollback steps:
   - remove Gemma-specific adjacent-user collapse and the outbound request-shape telemetry fields
   - revert the Gemma-specific wording in the local prompting contract
3. Data/state recovery notes:
   - no durable data migration is involved; rollback is code-and-doc only

## Versioning Decision

- Version bump type: none at the Orket package level in this working change
- Effective version/date: 2026-04-03 contract change
- Downstream impact:
  - LM Studio Gemma turn artifacts now expose request-role telemetry
  - operators should expect the admitted Gemma lane to send one `system` turn plus one merged `user` turn for these governed tool-call steps
