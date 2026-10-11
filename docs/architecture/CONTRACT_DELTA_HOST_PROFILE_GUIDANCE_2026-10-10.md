# Host prompt-profile guidance

Owner: Orket Core. Date: 2026-10-10. Core 0.8.6; SDK 0.8.0 unchanged.

The conservative `E_MODEL_INPUT_BUDGET` diagnostic now names the existing
`ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` and `context_budget_tokens` settings.
`MODEL_GENERATION_OPTIONS.md` documents an operator-owned registry and API host
restart, including the distinction from Gardener's command-harness limits.

This is compatible diagnostic guidance. Error codes, HTTP envelope/status,
admission calculations, packaged defaults, provider requests and completion
authority are unchanged. No migration is required. Raising context remains an
explicit host decision within model capacity; it does not guarantee report truth.

Verification: the real HTTP API/SDK path refuses the same prompt with 8192 context
and sends its complete system/user messages with 32768 and truncation guards.
The provider response in these controls is synthetic. The documented registry
commands are checked separately against an installed environment. Evidence and
limits: `docs/releases/0.8.6/PROOF_REPORT.md`.

Rollback may remove the diagnostic/guide addition together; it must retain the
existing full-input refusal and transport guards.
