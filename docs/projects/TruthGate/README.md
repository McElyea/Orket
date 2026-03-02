# TruthGate

Date: 2026-03-01

## Purpose

Replace TextMystery's template-only NPC response system with LLM-backed generation validated by a truth gate. NPCs respond freely via local LLM (Ollama). A truth gate checks each response against world state: no lies, no leaked guards, no self-incrimination. Time-budgeted retries with rejection feedback. Templates become last-resort fallback only.

## Canonical Docs

1. This README
2. `01-REQUIREMENTS.md` -- Requirements and gate rules

## Architecture

Three-layer integration: Orket SDK (LLMProvider protocol) -> TextMystery engine (TruthGate + render loop) -> CLI (Ollama adapter + wiring).

```
classify -> resolve -> [LLM generate -> truth gate validate -> retry] -> fallback to template
```

The gate validates, not generates. Classification and fact resolution remain deterministic. Only rendering is upgraded.

## SDK Modules

- `orket_extension_sdk/llm.py` -- LLMProvider protocol, GenerateRequest/Response, NullLLMProvider

## Engine Modules

- `textmystery/engine/truth_gate.py` -- TruthGate validator (leak, confession, lie, style checks)
- `textmystery/engine/npc_prompt.py` -- NPC system prompt builder from archetype + world state
- `textmystery/engine/llm_render.py` -- Time-budgeted generate-validate-retry loop
- `textmystery/engine/ollama_llm.py` -- Sync Ollama adapter implementing LLMProvider

## Graceful Degradation

1. LLM available + gate passes -> LLM text
2. LLM available + gate rejects all attempts -> template fallback
3. Ollama not running -> template fallback (zero latency cost)
4. No LLM provider -> template fallback (existing behavior)
5. SDK not installed -> template fallback (ImportError caught)

## Default Model

`llama3.1:8b` -- warm call latency ~300-500ms, fits in 8GB VRAM.
