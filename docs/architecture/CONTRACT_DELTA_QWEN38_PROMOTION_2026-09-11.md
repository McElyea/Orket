# Qwen3.8 Template and Promotion Contract Delta

## Summary

- Owner: Orket Core. Date: 2026-09-11.
- Contracts: `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`,
  `GOVERNED_AGENT_LOOP_V1.md`, `CURRENT_AUTHORITY.md`.

## Delta

The exact Qwen3.8 profile uses the packaged `qwen38_text_chatml.jinja` override.
It preserves text and declared roles with ChatML markers, disables thinking in
the generation prefix, and has no content-triggered branches or native tool
injection. JSON-wrapper tool calls remain the admitted host protocol.
The operator must select this template when launching llama-server.

Before each profiled generation, the adapter compares actual server template
bytes and model alias, independently checks `/apply-template`, hashes the LP-02
canonical render, and checks `/tokenize` against the profile/server context limit
including reserved output tokens. The existing deterministic history reduction
remains; a remaining oversized prompt fails closed using native token counts.
Unknown or mismatched template/render identity cannot count as successful proof.

Template audits now reject missing bytes and unapproved branches. Whitelists
bind a template digest to a named reviewer and approval reference; promotion
requires an audit bound to both the profile row and measured rendered template.
Tool corpus cases validate the actual requested tool and arguments. Conformance
retains every response and render receipt, closes its clients, and labels
unmeasured sampling properties honestly. Runtime sampling proof is separate.

Corrective prompts now include stable validator error details and the prior
output excerpt hash. Empty governed-agent continuation replay reports
`no_decisions`, while populated replay retains `matched`/`mismatch` semantics.

## Migration Plan

1. Use upstream llama.cpp `b10809` (`5266f24da`), the exact model alias and packaged
   template. The verified launch command is in `docs/RUNBOOK.md`.
2. Caching is enabled with `--cache-prompt --cache-ram 8192`; the older build's
   cache-disabling workaround is historical evidence, not the current setting.
3. Run the promotion corpus, runtime/repair proofs, source integration, installed
   acceptance and regression gates. Promotion is recorded only after these pass.
4. This is a source/installed-candidate change against tagged core 0.6.1, SDK
   0.6.0 and external extension 0.2.0; no new release is claimed by this record.
   The subsequent core 0.6.2 release and exact artifact acceptance are recorded
   in `docs/releases/0.6.2/PROOF_REPORT.md`.

## Rollback Plan

If the pinned setup fails, stop affected inference and retain failed evidence.
Restore the prior profile and server configuration together; never retain a
promotion claim while substituting the old runtime/template. The previous binary
and no-cache launch configuration remain available on this workstation.
No database migration is required. Existing run configuration remains immutable.

## Versioning Decision

Template version: `orket_qwen38_text_chatml_2026_09`; profile ID remains
`llama_cpp.qwen3.8.chatml.v1`. Operator migration is required. Other models and
explicit providers retain their own profiles and admission gates. Promotion does
not establish general coding-objective verification or hostile-code containment.
