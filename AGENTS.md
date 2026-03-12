# AGENTS.md

## Priority

1. truthful behavior
2. truthful verification
3. preserving future shippability
4. reducing authority drift
5. minimal-scope changes
6. resource efficiency

Exploratory work is not permission for low standards, duplicate authority, stale docs, false-green tests, unsafe fallbacks, or unclear entrypoints.

## Maintenance Rule

Any new AGENTS rule must replace or merge with an existing rule. Do not append overlapping policy.

## Scope

These rules apply to all new and modified code and docs.

1. Do not introduce new violations.
2. Do not widen existing violations.
3. When touching a non-compliant area, make the smallest reasonable move toward compliance that fits the task.
4. If pre-existing drift blocks the task, report it under `Remaining blockers or drift`.

## Session Gate

Before substantive work, read `docs/CONTRIBUTOR.md` in the current session, then follow its startup protocol exactly. Do not improvise contributor workflow or roadmap semantics outside `docs/CONTRIBUTOR.md`.

## Response and Link Format

Use client-surface link rules.

These rules override more general file-link defaults for this repo.

1. Codex app: workspace-relative Markdown links such as `[docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md)`.
2. VS Code / CLI: absolute Windows Markdown links such as `[Guide](/C:/Source/Orket/docs/CONTRIBUTOR.md)`.
3. Do not use `file://`.
4. Do not fall back to plain backticked paths until workspace-relative links have failed in the current thread and the user has reported that failure.

## Repo Discipline

1. Work directly on `main` unless the user explicitly requests a branch workflow.
2. If the user says commit or push "ALL changes", stage repository-wide with `git add -A` unless the user excludes paths.
3. Preserve future packaging and shipping options.
4. Do not introduce avoidable install, runtime, or test drift.
5. Prefer the smallest truthful change. Separate required work, confidence-improving work, and optional cleanup. If the user signals that the work seems off, too deep, or not focused on the right problem, stop and reassess at a higher level before continuing. Do not placate, restate the current frame more confidently, or keep refining the same track without addressing the scope concern directly.
6. Do not use "experimental" as permission for duplicated canonical behavior, stale active docs, ambiguous authority, or unclear runtime entrypoints.

## Roadmap Control

`docs/ROADMAP.md` is the active execution index.

1. Keep roadmap entries execution-only. Process rules live in `docs/CONTRIBUTOR.md`.
2. Follow roadmap hygiene, closeout, archive, and contract-extraction rules from `docs/CONTRIBUTOR.md`.
3. If a task changes contributor workflow or roadmap maintenance expectations, update `docs/CONTRIBUTOR.md` in the same change unless the user explicitly says not to.
4. When the user explicitly says to put or add something on the roadmap, place it in `Priority Now` at the highest available non-blocking position.
5. Do not move an explicit user-requested roadmap item to backlog or future lanes unless the user explicitly asks for backlog placement.
6. For explicit roadmap add or move requests, the completion response must include:
   - the full updated `Priority Now` block,
   - explicit confirmation the item does not appear in unintended sections,
   - the result of `python scripts/governance/check_docs_project_hygiene.py`.
7. If exact requested placement cannot be completed, stop and report the blocker instead of improvising a different placement.

## Authority and Drift

1. `CURRENT_AUTHORITY.md` is the canonical authority snapshot.
2. If a task changes install or bootstrap commands, runtime entrypoints, canonical test commands, active specs, script output locations, security boundaries, provider or runtime selection, or integration behavior, update the source of truth in the same change unless the user explicitly says not to.
3. Do not allow silent drift between code, docs, scripts, tests, and actual runtime behavior.
4. Report unresolved drift under `Remaining blockers or drift`.

## Testing and Verification

1. Prefer the highest practical test layer that exercises real behavior.
2. Label each new or modified test as `unit`, `contract`, `integration`, or `end-to-end`.
3. Do not present mock-heavy or structural tests as proof of runtime truth.
4. For real-path bug fixes, prefer contract or integration proof over implementation-detail tests.
5. For new or changed integrations, automations, or runtime or integration behavior, run the real flow end-to-end before declaring completion.
6. Record the observed path as `primary`, `fallback`, `degraded`, or `blocked`.
7. Record the observed result as `success`, `failure`, `partial success`, or `environment blocker`.
8. If live verification is impossible, say so explicitly and report the exact blocker.
9. Import-only, compile-only, dry-run-only, mocked success, or code inspection alone are not live proof.

## Script Output Convention

Any new script that writes rerunnable JSON results must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.

1. Keep one stable canonical output path per script.
2. Reruns append `diff_ledger` entries instead of creating timestamp-only files.
3. Default major-diff rollover:
   - `paths_total_reference <= 250`: `0.93`
   - `251-1200`: `0.88`
   - `>1200`: `0.80`
4. Rollover also requires `churn_paths >= 20`.
5. If you override thresholds or minimum changed paths, add a short code comment explaining why.

## Effort

Use the lowest reasoning tier that can reliably finish the task.

1. Retrieval, grep, and targeted file discovery: use the current session model at `low` effort.
2. Coding, editing, and targeted execution: use the current session model at `medium` effort.
3. Architecture, repo-wide refactors, and deep reviews: use the current session model at `xhigh` effort.
4. Do not spend `xhigh` on basic retrieval.

## Code Discipline

### Async-reachable paths

1. Do not use `subprocess.run()` or `subprocess.call()`.
2. Do not use `Path.read_text()`, `Path.write_text()`, or raw `open()`.
3. Do not use sync HTTP clients such as `requests`.
4. Do not use `time.sleep()`.
5. Do not put `lru_cache` on sync-to-async bridge functions.
6. If reachability is ambiguous, assume the path is async-reachable.

Use `asyncio.create_subprocess_exec()`, `aiofiles`, `AsyncFileTools`, `await asyncio.to_thread(...)`, `httpx.AsyncClient`, and `await asyncio.sleep()` as appropriate.

### Size and structure

1. Do not create a new Python file over 400 lines.
2. Do not grow an existing Python file past 400 lines unless required for correctness or explicitly approved.
3. When touching an oversized file, avoid making it larger unless unavoidable.
4. No new function should exceed 70 lines without clear justification.
5. No new class should expose more than 10 public methods.
6. Keep each FastAPI router focused on one resource domain where practical.

### Single source of truth

1. Do not duplicate definitions when one authoritative definition can be imported.
2. Do not add compatibility shims without explicit user approval or a tracked removal ticket.
3. Do not copy-paste a function and rename it when shared logic can be extracted.

### Exceptions and security

1. Do not use bare `except Exception` except at true top-level boundaries such as CLI entrypoints, API endpoints, background loops, or supervisors.
2. At those boundaries, log enough context to diagnose the failure.
3. Catch the narrowest reasonable exception type.
4. Never silently swallow exceptions.
5. Never embed credentials in URLs, logs, traces, or interpolated strings.
6. Never pass unsanitized user input to subprocess commands.
7. Never use `importlib.exec_module()` on user-controlled paths without OS-level sandboxing.
8. Use `Path.is_relative_to()` for path containment checks. Do not use `str.startswith()`.

### Naming and proxy rules

1. Do not introduce new `__getattr__` delegation.
2. Do not expand existing `__getattr__` forwarding. Remove it when the touched area is already being refactored.
3. Module-level singleton proxy or lazy-init patterns are allowed only with a short explanatory comment.

## Review and Reporting

1. Final task reports must be ordered as:
   - what changed,
   - what was verified,
   - what was not verified,
   - remaining blockers or drift,
   - exact files touched.
2. State whether proof is live, structural, or absent.
3. For reviews, prioritize findings over summary and group them as `Ship-risk debt`, `Exploration-safe debt`, and `Self-deception debt`.
4. When two approaches both work, choose the one that is easier to verify and less likely to create false confidence.
