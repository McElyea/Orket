# Contract Delta: Gemma OpenAI Tool-Turn Conformance

## Summary

- Change title: tighten Gemma tool-turn compaction, guard native-tool declaration fallback, and parser allowlisting for LM Studio
- Owner: Orket Core
- Date: 2026-04-03
- Affected contract(s):
  - `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
  - `CURRENT_AUTHORITY.md`
  - `orket/adapters/llm/local_prompting_policy.py`
  - `orket/adapters/llm/openai_native_tools.py`
  - `orket/application/workflows/turn_response_parser.py`

## Delta

- Current behavior:
  - after the Gemma message-shape fix, `CWR-01` and `CWR-02` could complete, but multi-write coder turns still overran the LM Studio context ceiling or produced undeclared or duplicate native tool calls
  - an earlier live guard run `a13f797e` at `.tmp/gemma_probe_live5/` still failed on `CWR-01` turn `002_integrity_guard`, where Gemma returned `finish_reason: "length"`, `openai_native_tool_names: []`, `openai_tool_choice: null`, and only length-capped reasoning text instead of tool calls
  - that old `requirements.txt` file was first-write evidence only, not truthful issue completion, because the guard never reached read-and-certify behavior
  - the observed pre-change blocker on live run `d41da4bc` was `CWR-03` turn `005_coder`, where Gemma returned `finish_reason: "length"`, `prompt_tokens: 3953`, `total_tokens: 4096`, and no tool calls
  - no Gemma-authored Python source files existed yet on that lane
- Proposed behavior:
  - the admitted Gemma lane keeps native function calling bounded to declared-path `read_file` and `write_file` schemas with `reasoning_effort=none`
  - guard/native turns recover bounded `read_file` declaration from artifact-contract and verification-scope read surfaces when explicit required-path lists are empty
  - Gemma multi-write tool turns use a tighter deterministic effective context cap than the profile base budget so tool-call headroom survives on LM Studio's currently observed 4096-token ceiling
  - provider-recorded native-tool telemetry is the authoritative parser allowlist, so undeclared Gemma-emitted native actions are filtered and exact duplicate calls are removed before execution
- Why this break is required now:
  - the runtime needs repeatable local-bot behavior on a real local model, not one-off first-write success
  - Gemma 4 supports native system prompts and function calling, but the local lane still needed stricter prompt compaction and post-parse discipline to stay inside the provider ceiling and avoid hallucinated extra calls

## Observed Live Evidence

Observed on 2026-04-03:

1. Preconditions before this conformance step:
   - live run `a13f797e` at `.tmp/gemma_probe_live5/` stopped on `CWR-01`
   - `002_integrity_guard` recorded `finish_reason: "length"`, `openai_native_tool_names: []`, `openai_tool_choice: null`, and `tool_calls: []`, while its prompt still required `read_file` plus `update_issue_status`
   - the resulting `.tmp/gemma_probe_live5/agent_output/requirements.txt` was not guard-certified; the run died on `progress contract not met after corrective reprompt`
   - live run `d41da4bc` at `.tmp/gemma_probe_live9/` stopped on `CWR-03`
   - `005_coder` recorded `openai_request_role_sequence: ["system", "user"]` but still hit `prompt_tokens: 3953`, `total_tokens: 4096`, `finish_reason: "length"`, and `tool_calls: []`
   - no files existed yet under `.tmp/gemma_probe_live9/agent_output/challenge_runtime/`
2. Postconditions after the conformance step:
   - fresh live rerun `4809bab0` at `.tmp/gemma_guard_fix_live/` no longer dead-stopped on `CWR-01`
   - `002_integrity_guard` recorded `prompt_tokens: 2677`, `finish_reason: "tool_calls"`, `openai_native_tool_names: ["read_file"]`, `openai_tool_choice: "required"`, and `openai_request_role_sequence: ["system", "user"]`
   - Gemma still over-emitted undeclared native actions on that turn, but parser diagnostics recorded the extra `update_issue_status` and `add_issue_comment` calls as `undeclared_tool` and accepted only the declared `read_file`
   - the parsed turn then closed truthfully with:
     - `.tmp/gemma_guard_fix_live/observability/4809bab0/cwr-01/002_integrity_guard/parsed_tool_calls.json`
     - `.tmp/gemma_guard_fix_live/observability/4809bab0/cwr-01/002_integrity_guard/tool_result_update_issue_status_97d112716032.json`
   - `CWR-02` prompt state in `.tmp/gemma_guard_fix_live/observability/4809bab0/cwr-02/004_integrity_guard/messages.json` recorded dependency status `CWR-01: done`, proving the old first-write-only seam is gone
   - fresh live rerun `7d131144` at `.tmp/gemma_probe_live10/` completed `CWR-03` and reached `CWR-04`
   - `005_coder` recorded `prompt_tokens: 2677`, `total_tokens: 3097`, `finish_reason: "tool_calls"`, warnings `context_trimmed:4`, `context_budget_cap:gemma_multi_write:2400`, and `message_shape:user_blocks_collapsed:6`, then wrote:
     - `.tmp/gemma_probe_live10/agent_output/challenge_inputs/workflow_valid.json`
     - `.tmp/gemma_probe_live10/agent_output/challenge_inputs/workflow_cycle.json`
     - `.tmp/gemma_probe_live10/agent_output/challenge_inputs/workflow_retry.json`
   - `007_coder` recorded `prompt_tokens: 2633`, `total_tokens: 3060`, `finish_reason: "tool_calls"`, warnings `context_trimmed:9`, `context_budget_cap:gemma_multi_write:2400`, and `message_shape:user_blocks_collapsed:3`, then wrote the first Gemma-authored Python source files:
     - `.tmp/gemma_probe_live10/agent_output/challenge_runtime/__init__.py`
     - `.tmp/gemma_probe_live10/agent_output/challenge_runtime/models.py`
     - `.tmp/gemma_probe_live10/agent_output/challenge_runtime/loader.py`
   - `008_coder` performed the corrective repair turn for `CWR-04` and rewrote `models.py` to remove the earlier `retIS` typo while preserving the same package surface
3. Turn milestones on the live lane:
   - first Gemma file write: turn `001_coder` (`requirements.txt`)
   - first successful multi-write artifact pack: turn `005_coder` (`workflow_*.json`)
   - first Gemma-authored program files: turn `007_coder` (`challenge_runtime/*.py`)
   - first program-file repair turn: turn `008_coder`
4. Remaining blocker after the change:
   - the overall live run still ended `terminal_failure` after the second `CWR-04` coder turn, so this milestone proves first code-writing success and repairability, not full epic completion

## Migration Plan

1. Compatibility window:
   - no compatibility window is needed for the admitted Gemma LM Studio lane because the previous behavior was a failing local-provider seam, not a desired external contract
2. Migration steps:
   - expose bounded native `read_file` and `write_file` schemas only for declared path surfaces
   - recover guard/native `read_file` declaration from artifact-contract and verification-scope read surfaces when explicit required-path lists are absent
   - tighten effective context budget on Gemma multi-write tool turns
   - treat recorded native-tool telemetry as authoritative when filtering undeclared and duplicate native tool calls before execution
   - record the first live code-writing milestone and turn counts as durable contract evidence
3. Validation gates:
   - targeted prompt-policy and parser tests
   - fresh live rerun of `python main.py --epic challenge_workflow_runtime --workspace .tmp/gemma_probe_live10 --build-id gemma_probe_live10 --model google/gemma-4-26b-a4b`
   - direct import proof from `.tmp/gemma_probe_live10/agent_output`: `python -c "from challenge_runtime import load_workflow; data = load_workflow('challenge_inputs/workflow_valid.json'); print(data['workflow_id']); print(data['tasks'][3]['deps'])"`

## Rollback Plan

1. Rollback trigger:
   - Gemma regresses back to length-capped multi-write turns or native tool-call drift returns on declared-interface turns
2. Rollback steps:
   - remove the Gemma-specific multi-write effective budget cap
   - revert Gemma native tool exposure to the previous bounded surface
   - remove undeclared-tool filtering or duplicate native-call dedupe only if a narrower corrective path replaces them
3. Data/state recovery notes:
   - no durable data migration is involved; rollback is code, tests, and docs only

## Versioning Decision

- Version bump type: none at the Orket package level in this working change
- Effective version/date: 2026-04-03 contract change
- Downstream impact:
  - operators can now verify a truthful first-code-writing Gemma lane using `.tmp/gemma_probe_live10/`
  - the admitted Gemma lane now has explicit preconditions, postconditions, and turn milestones for first write, first multi-write artifact pack, first program files, and first repair turn
