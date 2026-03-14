# Claim E Resolution Note

## What was wrong

1. Published Claim E still failed strict compare on equivalent fresh live runs, with operator-visible drift in `requirements.txt`, `design.txt`, and `main.py`.
2. The failing path also contained legacy runtime and adapter mismatches: required-tool turns were routed through the stochastic `concise_text` bundle, the legacy non-protocol fence validator rejected valid tool turns, architect prompts still described free-form design output, and legacy Ollama `tool_call` turns were clamped to a single JSON object.
3. After those authored-output fixes landed, unfiltered compare still failed only on runtime-generated support artifacts and fresh session identity, which meant the prior compare claim was too broad for the live evidence.

## What changed

1. Required-tool turns now resolve to the deterministic `tool_call` local prompting bundle even without protocol governance.
2. Legacy non-protocol tool turns no longer fail on the protocol-only markdown-fence validator.
3. Architect and reviewer prompt assets now align to the JSON artifact and read-path contracts used by the runtime.
4. Ollama `format=json` is now reserved for `strict_json` turns so legacy `tool_call` turns can emit repeated top-level tool-call objects.
5. Strict compare now ignores fresh `session_id` identity when governed replay state otherwise matches, and the governed compare surface excludes runtime-generated support artifacts `observability/runtime_events.jsonl`, `verification/runtime_verification.json`, and `**/__pycache__/*.pyc`.

## What the new evidence shows

1. Fresh live runs `66a2e31c`, `2855ce28`, and `8a1e9bb3` all completed successfully.
2. Pairwise strict compare under the final governed scope passed for `A/B`, `A/C`, and `B/C` with `deterministic_match=true`.
3. Replay on run `66a2e31c` returned `status=done` with `compatibility_validation.status=ok`.
4. Provider preflight passed on Ollama `qwen2.5-coder:7b`.
5. The pre-resolution compare artifact and the post-fix unfiltered compare artifact remain in this packet to show both the original operator-visible drift and the narrowed runtime-generated support-artifact drift.

## What remains

1. Nothing remains open for DD03142026.
2. Any future attempt to widen the deterministic compare surface must land as a new governed contract change with fresh live proof.
