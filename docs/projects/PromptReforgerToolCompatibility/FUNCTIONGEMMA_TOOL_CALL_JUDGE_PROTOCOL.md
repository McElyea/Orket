# FunctionGemma Tool-Call Judge Protocol

Owner: Orket Core
Status: Active bootstrap protocol
Last updated: 2026-04-04

## Purpose

Define the first bounded advisory judge protocol for the Prompt Reforger Gemma tool-use lane.

This protocol does not replace Orket parser, validator, or turn-contract authority.
It defines only the evidence packet and advisory verdict shape that the first `FunctionGemma` judge path must use.

## Scope

This protocol applies only to the bounded bootstrap corpus at:

- `docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json`

The first judge slice is limited to challenge-workflow tool turns and review turns drawn from `challenge_workflow_runtime`.

## Judge Inputs

Every judge decision must bind to exactly one exercised slice and one observed turn packet:

1. `slice_id`
2. `issue_id`
3. `role_name`
4. `required_action_tools`
5. `required_read_paths`
6. `required_write_paths`
7. `required_statuses`
8. exact model-facing prompt reference
9. exact raw model output reference
10. exact parsed tool-call reference
11. exact parser-diagnostics reference

## Advisory Evaluation Dimensions

The judge must evaluate only these bounded dimensions:

1. `tool_selection`
2. `argument_presence`
3. `argument_shape`
4. `extra_undeclared_tool_calls`
5. `malformed_output_shape`

No broader prompt-quality or coding-quality verdict is admitted.

## Advisory Verdict Shape

Each advisory verdict must be emitted through exactly one native tool call:

1. tool name:
   - `emit_judgment`
2. transport rule:
   - the judge may not answer in prose when the native tool path is available
   - the stored lane artifact may normalize the tool arguments back into the canonical nested verdict record below

The normalized advisory verdict record must emit:

1. `slice_id`
2. `judge_model_identity`
3. `judge_provider`
4. `judge_quantization`
5. `verdict`
   Allowed values:
   - `pass`
   - `fail`
   - `inconclusive`
6. `dimension_results`
7. `notes`
8. `evidence_refs`

### Native Tool Argument Contract

The admitted `emit_judgment` tool-call arguments are:

1. `verdict`
2. `tool_selection`
3. `argument_presence`
4. `argument_shape`
5. `extra_undeclared_tool_calls`
6. `malformed_output_shape`
7. `rationale`

Each verdict-bearing field must be:

- `pass`
- `fail`
- `inconclusive`

## Authority Rule

Judge outputs are evidence only.

Canonical acceptance still remains with:

1. Orket tool parsing,
2. turn-contract validation,
3. required read/write path enforcement,
4. issue-status update verification,
5. measured run artifacts.

If the judge disagrees with parser or validator truth, parser and validator truth win.
