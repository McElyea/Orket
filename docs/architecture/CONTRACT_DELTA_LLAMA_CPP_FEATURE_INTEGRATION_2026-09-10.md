# Contract Delta: llama.cpp Feature Integration

## Summary

- Owner: Orket Core.
- Date: 2026-09-10.
- Affected authorities: `docs/CONTRIBUTOR.md`, `CURRENT_AUTHORITY.md`,
  `docs/specs/GOVERNED_AGENT_LOOP_V1.md`,
  `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`, `docs/RUNBOOK.md`.
- Request: make llama.cpp a first-class provider across governed agents and
  other features missed by the original adapter implementation.

## Delta

| Surface | Previous gap | Current behavior |
| --- | --- | --- |
| Governed CLI | Only fixture or `--ollama-model` | Generic `--model`, `--provider`, and `--provider-base-url`; llama.cpp is the generic default |
| API supervisor and all wake sources | Provider mode admitted only Ollama/fixture | Shared local-provider configuration supports llama.cpp, LM Studio, Ollama and OpenAI-compatible servers |
| API startup | First claim could race scheduled ingress while enabling SQLite WAL | Await wake-store initialization before starting the supervisor or admitting ingress |
| Continuation and effect resume | Ollama-specific composition | Same exact provider/model configuration is retained through wake, checkpoint and resume |
| Model receipts | Only Ollama finish-reason extraction | OpenAI-compatible finish reason, truncation and measured usage; requested provider identity preserved |
| Text model calls | Invalid task class and JSON-only response parsing | Valid concise-text policy and actual text responses |
| Runtime target | A blocked target with a nonempty model could be cached | Blocked targets fail before caching; admitted governed targets are pinned against reselection |
| Streaming workload | llama.cpp rejected by start validation | Shared provider allowlist, actual provider health identity, blocked-target rejection |
| Streaming tooling | Missing choices and wrong endpoint/evidence identity | Shared allowlist and evidence helper preserve llama.cpp and LM Studio lineage |
| Model listing and quant wrapper | Missing llama.cpp choice/default or wrong endpoint variable | Explicit llama.cpp selection and correct provider endpoint wiring |
| ODR baseline/comparison | llama.cpp resolved to Ollama endpoint | Canonical endpoint resolution and truthful operator-owned residency |
| Qwen3.8 profile | No admitted exact model match | `llama_cpp.qwen3.8.chatml.v1` for `orcarouter_qwen3.8-27b-uncensored-q4_k_l` |

The provider composition moved from an Ollama-named adapter into application
services, removing its adapter-to-application dependency. It reuses the canonical
runtime target resolver and existing transport; it adds no second provider
implementation. Inventory failure is a classified configuration error, and
cross-provider model settings cannot silently redirect a governed run.

The audit also inspected the generic SDK capability, extension runtime,
provider extractors, quarantine policy, profile registry, local-prompting
conformance, companion provider matrix, and general quant runner. These already
delegate to the common local provider or accept the canonical provider tokens.
Provider-specific Ollama/LM Studio lifecycle tools and the explicitly paired
Ollama-versus-LM-Studio codegen experiment retain their defined scope.

## Migration Plan

1. Use `--provider llama_cpp --model <exact-served-alias>` for CLI submission.
   Use the generic governed-agent provider/model/base-URL environment variables
   in the runbook for API-owned work. Existing Ollama flags and environment
   settings remain supported; an existing Ollama model setting still selects
   Ollama when no API provider is specified.
2. Keep the operator-owned llama-server running. The served alias must match
   the lowercase GGUF filename stem and an admitted prompt profile. The current
   Qwen3.8 text profile expects an 8192-token context and disabled reasoning.
   The local `dd7cad7` server build aborted while reusing recurrent prompt-cache
   state; the verified launch uses `--no-cache-prompt --cache-ram 0`.
3. Do not migrate an existing run to a different configuration. Provider changes
   require a new run. Old snapshots that recorded the installed Ollama client
   library as a provider version cannot be rewritten into server attestations;
   drain such runs with their original runtime before upgrading.
4. Validate contracts, real extension execution, API wake/replay, effects across
   restart, streaming and ODR paths. The canonical rerunnable integration command
   is `scripts/proof/run_llama_cpp_integration.py`; its stable receipt is
   `benchmarks/results/providers/llama_cpp_integration.json`.

## Proof Boundaries

The live path is `primary`; proof records success or failure from actual test
results and retained SQLite receipts. It uses the real external extension and
operator-managed Qwen3.8 server. It is source-worktree integration proof, not a
new installed release, multi-model capacity claim, performance comparison, or
production soak. Quant wrapper coverage proves selection/wiring, not completion
of a full model sweep. Formal local-prompt profile promotion still requires the
existing 1000-case JSON, 500-case tool and template-audit gates.

## Rollback Plan

1. Trigger: regression in exact identity, provider routing, receipts, or effect
   recovery.
2. Drain affected runs, restore the prior runtime and its matching configuration,
   then use explicit Ollama settings for new runs if needed.
3. Preserve all durable run/effect records; do not rewrite configuration digests
   or retry already-observed effects to force compatibility.

## Versioning Decision

- Additive CLI/configuration behavior; SDK wire contracts remain v1.
- Existing Ollama inputs remain supported. The old internal Ollama-only provider
  module is replaced by application-owned composition without a compatibility shim.
- This worktree change does not publish a new package version or release.

## Architecture Review

AC-01 through AC-10: pass for the changed provider composition, identity,
admission, evidence and configuration paths. Existing interface-to-storage and
large transport-module debt is not widened. The small additions to the existing
large transport classes are required to bind admitted targets and retain actual
provider identity; shared script evidence was extracted to reduce duplication.
