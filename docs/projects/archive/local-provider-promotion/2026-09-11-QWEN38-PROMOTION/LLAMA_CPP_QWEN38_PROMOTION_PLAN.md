# llama.cpp Qwen3.8 Promotion and Runtime Readiness

Date: 2026-09-11. Status: Completed. Owner: Orket Core.

The user requested completion of the remaining llama.cpp work, specifically
removing the cache workaround and formal model promotion. Durable authority is
`docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`.

1. Preserve the known-working server and test a pinned upstream replacement with
   prompt caching enabled. Prove repeated prefixes, changed history, cancellation,
   streaming and governed-agent recovery before selecting it for normal use.
2. Capture actual template bytes, audit hidden branches/role changes/tool text,
   and compare server-rendered prompts with an independent local render. Repair
   false-green audit/readiness gates; do not waive suspicious triggers silently.
3. Run the real 1000-case JSON and 500-case tool promotion corpus, retain output
   and identity evidence, and enforce the existing thresholds and drift gates.
4. Run bounded workload/soak and installed acceptance on the final server/profile,
   document exact proof limits, and update current authority and operator setup.
5. Close/archive this lane only when its gates pass; otherwise retain exact
   failing evidence and executable next steps. Broader arbitrary-objective or
   hostile-code claims cannot be inferred from profile conformance.

Evidence uses canonical rerun-ledger paths under
`benchmarks/results/protocol/local_prompting/qwen38_promotion/` and the existing
governed-agent integration/acceptance receipts. Initial local server is build
`dd7cad7`, running without prompt caching; model alias is
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`.

Closeout: all five steps passed. Full proof and limits are recorded in
`docs/architecture/LLAMA_CPP_QWEN38_PROMOTION_VERIFICATION_2026-09-11.md`.
The cache workaround is removed, the exact profile is promoted, and the source
and installed bounded agent paths passed with llama.cpp as the default.
