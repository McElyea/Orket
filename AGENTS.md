# AGENTS.md

## Purpose

This repository is exploratory, but it is not exempt from engineering discipline.

Orket is used to explore local LLM workflow, orchestration, tooling, runtime behavior, and future product possibilities. Agents must support experimentation without increasing drift that would make future shipping harder.

Optimize for:
1. truthful behavior,
2. truthful verification,
3. preserving future shippability,
4. reducing authority drift,
5. minimal-scope changes,
6. resource efficiency.

Do not confuse:
- exploratory code with low standards,
- broad scope with lack of boundaries,
- green tests with real proof.

---

## Enforcement Scope

These rules are binding for all new and modified code.

Existing violations may remain temporarily only when they are outside the scope of the current task. Agents must not:
1. introduce new violations,
2. expand the scope of an existing violation,
3. move code further away from compliance when touching an affected area.

When modifying a non-compliant file, make the smallest reasonable improvement toward compliance unless the user explicitly directs otherwise.

Scope precedence rule:
Make the smallest reasonable compliance improvement that fits inside the current task. Do not use compliance work as a reason to perform unrelated cleanup or broad refactoring.

If a task is blocked by a pre-existing violation, report it under:
`Remaining blockers or drift`.

Do not treat existing violations as permission to create more.

---

## Response Formatting

When referencing files in chat responses, choose link format by client surface.

### VS Code Extension / CLI Surface

Use clickable Markdown links with absolute Windows paths in URL form.

Preferred style:
1. `[Label](/C:/absolute/path/to/file.ext)`
2. Example: `[Local Prompting Contract](/C:/Source/Orket/docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)`
3. Example with line suffix when supported: `[File:120](/C:/Source/Orket/docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md:120)`

Rules:
1. Prefer `/C:/...`.
2. Do not use `file://` links.
3. Do not use plain backticked paths unless the user explicitly requests plain paths.

### Codex App Surface

If the active surface is the Codex app and file links are meant to open inside VS Code from the app, use workspace-relative Markdown links instead of absolute Windows-path URL links.

Preferred style:
1. `[CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)`
2. `[Provider Runtime Target](orket/runtime/provider_runtime_target.py)`
3. `[Contributor Guide](docs/CONTRIBUTOR.md)`

Rules:
1. Prefer repo-relative targets rooted at the current workspace.
2. Do not use `/C:/...` targets in the Codex app surface unless the user explicitly confirms they work again.
3. Do not use `./` or `.\` prefixes unless required by a specific client quirk.
4. If the user reports link translation drift, fall back to plain backticked Windows paths for that thread until a working style is re-confirmed.

---

## Repo Discipline

Orket may remain broad and exploratory, but agents must not normalize preventable shipping debt.

Required:
1. Preserve future packaging and shipping options.
2. Do not introduce avoidable install/runtime/test drift.
3. Do not leave behind ambiguous authoritative paths when a task touches one.
4. Do not treat "experimental" as permission for:
   - broken dependency authority,
   - stale docs on active paths,
   - false-green testing,
   - duplicated canonical behavior,
   - unsafe fallbacks,
   - unclear runtime entrypoints.

Allowed:
1. Broad exploratory surfaces.
2. Incomplete product packaging in non-authoritative areas.
3. Prototype code that is clearly labeled and does not masquerade as the canonical path.

---

## Contributor Process Authority (Required)

`docs/CONTRIBUTOR.md` is the canonical contributor workflow for this repository. Agents must follow it, not re-invent it in ad hoc roadmap prose.

Required:
1. Read and follow `docs/CONTRIBUTOR.md` when executing roadmap-driven work or updating documentation process.
2. Treat `docs/ROADMAP.md` as an active execution index, not a session journal, narrative handoff log, or duplicate process guide.
3. Keep roadmap entries terse, operational, and current by applying the roadmap hygiene rules already defined in `docs/CONTRIBUTOR.md`.
4. If a task changes contributor workflow or roadmap maintenance expectations, update `docs/CONTRIBUTOR.md` and any dependent instructions in the same change unless the user explicitly says not to.
5. Completed non-maintenance project lanes must not linger in active `docs/projects/`; move long-lived contracts/specifications to `docs/specs/` and archive the remaining lane material.
6. When accepted requirements already contain durable contracts/specifications, extract those into `docs/specs/` before writing the implementation plan so the plan cites stable authority instead of soon-to-be-archived requirement docs.

Do not use `docs/ROADMAP.md` to restate process that already lives in `docs/CONTRIBUTOR.md`.

---

## Authority and Drift Control (Required)

Agents must protect the repository's current authoritative paths.

Current authority snapshot:
1. `CURRENT_AUTHORITY.md` is the canonical map of what is authoritative right now.
2. If a task changes an authority item listed there, update `CURRENT_AUTHORITY.md` in the same change unless the user explicitly says not to.

Before declaring a task complete, check whether it affects any of these:
1. canonical install/bootstrap path,
2. canonical runtime entrypoint,
3. canonical test command,
4. active protocol/spec documents,
5. canonical script output locations,
6. security boundaries,
7. model/provider/runtime selection behavior,
8. integration behavior.

If a task changes one of those, update the corresponding source of truth in the same change unless the user explicitly says not to.

Do not allow silent drift between:
- `pyproject.toml`,
- `requirements.txt`,
- docs,
- scripts,
- tests,
- actual runtime behavior.

If drift is discovered and not fixed, report it explicitly under:
`Remaining blockers or drift`.

---

## Testing the Right Layer (Required)

False confidence is one of the highest-risk failure modes in this repository.

Agents must prefer tests that validate real runtime behavior over tests that only validate scaffolding, mocks, or internal implementation detail.

Required:
1. Label each new or modified test by layer:
   - unit,
   - contract,
   - integration,
   - end-to-end.
2. Do not present mock-heavy or structural tests as proof of runtime truth.
3. When fixing a bug in a real execution path, prefer the highest practical test layer that exercises the real behavior.
4. Flag tests that:
   - mock away the behavior under investigation,
   - assert implementation details instead of observable contracts,
   - rely on synthetic fixtures that bypass the real path,
   - pass while the live path is still broken.
5. When higher-layer proof is impractical, state the gap explicitly.

Preferred order:
1. integration or contract proof for real behavior,
2. targeted unit coverage for edge cases,
3. minimal mocks only where isolation is required.

Do not claim confidence the repo has not earned.

---

## Live Integration Verification (Required)

For any new or changed integration or automation path that changes runtime or integration behavior, the agent must verify behavior against the real configured system before declaring completion.

Applies to:
- CI,
- APIs,
- webhooks,
- runners,
- external services,
- provider integrations,
- cross-process orchestration paths.

Required proof:
1. Run the real command or flow end-to-end.
2. Record the observed path:
   - primary,
   - fallback,
   - degraded,
   - blocked.
3. Record the observed result:
   - success,
   - failure,
   - partial success,
   - environment blocker.
4. If it fails, capture the exact failing step and exact error.
5. Either fix it or report the blocker concretely.

Insufficient proof:
- compile-only,
- import-only,
- dry-run-only,
- mocked success,
- code inspection alone.

If live verification is impossible because credentials, infrastructure, or external dependencies are unavailable, say so explicitly and do not over-claim completion.

References:
1. `[CONTRIBUTOR.md](/C:/Source/Orket/docs/CONTRIBUTOR.md)`
2. `[AGENTS.md](/C:/Source/Orket/AGENTS.md)`

---

## Script Output Conventions (Required)

Any new script that writes rerunnable JSON results must use:
- `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger`, or
- `write_json_with_diff_ledger` for JSON text payloads.

Rules:
1. Keep a stable canonical output file path for each script output.
2. Reruns must append `diff_ledger` entries instead of creating timestamp-only files.
3. Default major-diff rollover policy:
   - `paths_total_reference <= 250`: threshold `0.93`
   - `251-1200`: threshold `0.88`
   - `>1200`: threshold `0.80`
4. Rollover also requires `churn_paths >= 20`.
5. If overriding thresholds or minimum changed paths, include a short code comment explaining why.

---

## Model Selection and Resource Efficiency

Use the minimum reasoning tier that can reliably complete the task.

Default model guidance for this repo:

1. **Search / Retrieval**
   - Model: `gpt-5.3-codex`
   - Effort: `low`
   - Use for: grep, file discovery, code reading, structure exploration, locating definitions.

2. **Coding / Execution**
   - Model: `gpt-5.3-codex`
   - Effort: `medium`
   - Use for: writing code, editing files, running tests, fixing bugs, targeted implementation.

3. **Planning / Architecture / Brutal Review**
   - Model: `gpt-5.3-codex`
   - Effort: `xhigh`
   - Use for: architecture decisions, cross-file refactors, repo-wide reasoning, deep code review, drift analysis.

Rules:
1. Prefer explicit naming:
   - `gpt-5.3-codex low`
   - `gpt-5.3-codex medium`
   - `gpt-5.3-codex xhigh`
2. Do not spend `xhigh` on basic retrieval.
3. Do not use broad file loading when targeted reads are enough.
4. Escalate reasoning effort only when the task justifies it.

---

## Change Scope Discipline

Prefer the smallest truthful change.

Required:
1. Do not perform broad cleanup unless the task requires it.
2. Do not refactor unrelated areas opportunistically.
3. If adjacent refactoring is required for safety or clarity, keep it narrow and explain why.
4. Separate:
   - required-for-correctness work,
   - confidence-improving work,
   - optional cleanup.

---

## Code Discipline (Required)

These rules are mandatory for new and modified code unless the user explicitly directs otherwise.

### Async Purity

Assume ambiguous call paths are async-reachable.

1. Never use `subprocess.run()` or `subprocess.call()` in async-reachable code. Use `asyncio.create_subprocess_exec()` or `await asyncio.to_thread(...)`.
2. Never use `Path.read_text()`, `Path.write_text()`, or raw `open()` in async-reachable code. Use `aiofiles`, `AsyncFileTools`, or `await asyncio.to_thread(...)`.
3. Never use sync HTTP clients such as `requests`. Use `httpx.AsyncClient`.
4. Never use `time.sleep()` in async code. Use `await asyncio.sleep()`.
5. Never place `lru_cache` on sync-to-async bridge functions.
6. If unsure whether a path is async-reachable, assume it is.

### File Size Limits

Large files are a maintainability hazard and should be reduced over time.

Required:
1. Do not create a new Python file over 400 lines.
2. Do not increase an existing Python file past 400 lines unless the user explicitly approves or the change is required for correctness and no reasonable split fits the task.
3. When touching an oversized file, avoid making it larger unless unavoidable.
4. Prefer extracting helpers or focused modules when an edited file is already oversized.
5. No new class should expose more than 10 public methods.
6. No new function should exceed 70 lines unless there is a clear justification.
7. Each FastAPI router file should own one resource domain where practical.

Existing oversized files are technical debt, not precedent.

### DRY / Single Source of Truth

1. Never duplicate definitions across files when one authoritative definition can be imported.
2. Never add a compatibility shim without a tracked removal ticket or explicit user approval.
3. Never copy-paste a function and rename it when common logic can be extracted.

### Exception Handling

1. Never use bare `except Exception` except at true top-level boundaries:
   - CLI entrypoints,
   - API endpoints,
   - background task loops,
   - process supervisors.
2. At top-level boundaries, log enough context to diagnose the failure.
3. Catch the narrowest reasonable exception type.
4. Never silently swallow exceptions.

### Security Boundaries

1. Never embed credentials in URLs, logs, traces, or interpolated strings.
2. Never pass unsanitized user input to subprocess commands.
3. Never use `importlib.exec_module()` on user-controlled paths without OS-level sandboxing.
4. Always use `Path.is_relative_to()` for path containment checks, never `str.startswith()`.

### Naming and Proxies

1. Do not introduce new `__getattr__` delegation to forward methods.
2. Existing `__getattr__` delegation must not be expanded and should be removed when the touched area is being refactored.
3. Proxy or lazy-init patterns are allowed only for module-level singletons and must include a short explanatory comment.

`__getattr__` forwarding is discouraged because it is invisible to IDEs, type checkers, and grep.

---

## Verification and Reporting

When finishing a task, report in this order:

1. what changed,
2. what was verified,
3. what was not verified,
4. remaining blockers or drift,
5. exact files touched.

Be precise:
1. If proof is structural only, say so.
2. If proof is live, say so.
3. If proof is absent, say so.

Do not overstate certainty.

---

## Preferred Review Framing

When asked for a review, group findings where relevant into:

1. **Ship-risk debt**
   - issues that would block safe shipping, trust, packaging, or operability.

2. **Exploration-safe debt**
   - acceptable mess while the repo remains exploratory.

3. **Self-deception debt**
   - anything that creates false confidence, including:
     - stale docs,
     - duplicate authority,
     - false-green tests,
     - mock-heavy proof of the wrong layer,
     - compile-only proof presented as runtime proof.

Prioritize self-deception debt aggressively.

---

## Decision Rule

Default priority order:

1. truthful behavior,
2. truthful verification,
3. preserving future shippability,
4. reducing authority drift,
5. minimizing scope,
6. resource efficiency.

If two approaches both work, choose the one that is easier to verify and less likely to create false confidence.
