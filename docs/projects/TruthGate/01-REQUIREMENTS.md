# TruthGate Requirements

## R1: LLMProvider SDK Protocol

The SDK must define an `LLMProvider` protocol with `generate(request) -> response` and `is_available() -> bool`. A `NullLLMProvider` fallback must return empty text and `is_available() == False`.

## R2: Truth Gate Validation

The truth gate validates LLM-generated NPC responses against world state with four checks (in order, short-circuiting):

1. **LEAK** -- Response must not reveal any fact in `npc_guards[npc_id]`. Fingerprints extracted from fact payloads (who, where, object, method, action, domain). Also checks `npc_secrets`.
2. **CONFESSION** -- Culprit NPC must not self-incriminate. Pattern-matched: "I did it", "it was me", "I'm guilty", "I moved the audit drive", etc.
3. **LIE** -- In ANSWER mode, if response mentions a time, it must match the fact's canonical time.
4. **STYLE** -- Word count within archetype `max_words` limit. Response must not be empty.

Each rejection returns a human-readable reason for the next retry prompt.

## R3: NPC System Prompts

Built from: archetype personality description, decision mode (ANSWER/REFUSE/DONT_KNOW), fact phrase (for ANSWER mode), word limit, guardrails. On retry, includes the rejection reason.

## R4: Time-Budgeted Retry Loop

Default 2000ms budget. Generates via LLM, validates via gate, retries with rejection feedback until budget exhausted. Falls back to template text on budget exhaustion.

## R5: Graceful Degradation

No Ollama, no model, SDK not installed, or gate rejects everything -- all fall back to existing template system seamlessly.

## R6: Determinism Preserved

`llm_provider=None` by default. Parity checks and golden tests never use LLM. Classification and fact resolution stay deterministic. Only rendering text is non-deterministic.

## R7: CLI Integration

`--llm-model` flag to select Ollama model (default: llama3.1:8b). `--no-llm` flag to force template-only mode. Status line shows backend readiness.

## R8: Ollama Adapter

Sync `OllamaLLMProvider` using `ollama.Client()` (not async). Probes model availability once at init. Returns empty on error (no exceptions bubble up).
