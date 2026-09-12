# Contract Delta: llama.cpp Defaults

## Summary

- Owner: Orket Core.
- Date: 2026-09-11.
- Request: make llama.cpp the default everywhere; local Ollama was deliberately removed.
- Authorities: `CURRENT_AUTHORITY.md`, `docs/CONTRIBUTOR.md`, `docs/RUNBOOK.md`,
  `docs/specs/GOVERNED_AGENT_LOOP_V1.md`, and the extension/provider matrix contracts.

## Delta

Provider-neutral entrypoints now share `orket/runtime/config/defaults.py`:
`llama_cpp`, with `orcarouter_qwen3.8-27b-uncensored-q4_k_l` as the local model.
This applies to the adapter, discovery, model selection, extension catalog and
generation, streaming, ODR, probes, acceptance helpers and general proof tooling.
The standard environment uses that GGUF alias. Explicit model/provider selections
remain authoritative. Multi-model campaigns require explicit model lists; the
default single-model campaign does not establish distinct-model capacity.
Installed-artifact acceptance also defaults to llama.cpp, including abrupt
process exit before/after writes; `--provider ollama` selects the legacy campaign.

An omitted API agent provider selects llama.cpp even when stale
`ORKET_GOVERNED_AGENT_OLLAMA_MODEL` variables remain. Unknown provider names fail
before transport creation. Unavailable llama.cpp does not cause another provider
to be selected. Missing summary evidence is marked with the existing missing-data
token instead of inventing an Ollama receipt.

Development and testing order is llama.cpp, LM Studio, then Ollama. Ollama-specific
adapters, explicit compatibility tests, historical evidence and intentionally
provider-specific experiments retain their identities. The legacy Ollama engine
recommendation catalog is consulted only when Ollama is explicitly selected;
discovery does not recommend unserved fallback models as installed models.

## Migration Plan

1. Run an operator-managed llama-server at `http://127.0.0.1:8080/v1`, or configure
   `ORKET_LLAMA_CPP_BASE_URL`. The exact served alias must match local GGUF inventory
   and an admitted prompt profile. For this Qwen model use 8192 context, Jinja,
   reasoning off, `--no-cache-prompt --cache-ram 0` with the current server build.
2. Existing Ollama users must explicitly select `ollama`, including
   `ORKET_GOVERNED_AGENT_PROVIDER=ollama` for legacy agent API model variables.
   Explicit `--ollama-model` remains an explicit provider selection.
3. Preserve existing durable runs and configuration digests. Drain old runs under
   their original runtime; provider changes require new runs.
4. Verify default selection contracts and real llama.cpp CLI/API continuation,
   effects, streaming, extension generation, discovery and ODR before handoff.

## Rollback Plan

On a default-selection regression, preserve evidence and restore the previous
runtime with its matching configuration. Do not silently redirect existing runs
or retry uncertain effects. Explicit provider selection remains available.

## Versioning Decision

This changes omission semantics and the default local model. It is source work;
no new version, tag or package publication is performed in this change. A future
release must document these migration requirements. SDK wire schemas are unchanged.

## Architecture Review

Existing runtime configuration ownership and provider inventory are reused;
discovery duplication is removed. No new async blocking I/O or provider fallback
is introduced. Existing oversized runtime modules shrink or retain their size.
Missing provider evidence remains missing rather than being inferred from the
new default. Broader architecture and quality-gate debt remains in the active
architectural-truth lane.
