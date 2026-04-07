# Orket Adapter Targets — Filtered 25

**Filter pass:** Removed stale repos, chatbox-adjacent projects, engine-heavy orchestration frameworks, closed-core-adjacent tools, and anything requiring engine surgery rather than adapter insertion.

**Architecture used as truth:** Orket's current seams are `Workload` + `WorkloadContext` protocol, `TurnLifecycleInterceptor` (before_prompt / before_tool / after_tool hooks), `ToolGate.validate()`, `OpenClawJsonlSubprocessAdapter` (JSONL subprocess bridge), and `CapabilityRegistry` (LLM, TTS, STT, Memory, ScreenRenderer capability providers). The BFF surface is `CompanionConfig` (mode/memory/voice sections). No generic governed-action contract exists yet.

**Notation for architecture fit:**
- ✅ Current: fits via existing Extension + BFF + Workload protocol without new contracts
- ⚠️ Future: requires a new governed-action contract or approval surface not yet in Orket
- ❌ Not a fit: would require engine surgery or replacing Orket's execution model

---

## Top 5 — Inspect These First

These have the narrowest, cleanest insertion seams and the most compelling governance value.

---

### #1 — `simonw/files-to-prompt`
**GitHub:** https://github.com/simonw/files-to-prompt
**Category:** CLI / file mutation tool
**Stars:** ~2.4k | **License:** Apache-2.0 | **Active:** 2025

**Why it survived:** It is thin. It does one governed thing — ingest file trees and produce structured prompt input. The seam is `ToolGate` + `TurnLifecycleInterceptor.before_tool` to intercept file reads, validate paths against a policy (no secrets, no out-of-bounds paths), record which files were included. There is no competing orchestration engine, no LLM of its own. It is a pure side-effect producer.

**Governed action seam:** File inclusion is a durable selection — what goes into the context window is a committed choice. Orket can wrap each file inclusion as a `ToolCall(tool="include_file", args={path: ...})` with an `EffectJournalEntryRecord` noting what was consumed.

**Architecture fit:** ✅ Current — fits as a `Workload` that calls a subprocess via `OpenClawJsonlSubprocessAdapter`. No new contracts needed.

**Main integration risk:** The tool is primarily a library/CLI, not a service. Adapter must be a thin subprocess wrapper. Risk that future versions change CLI flags and break the JSONL protocol.

---

### #2 — `nicowillis/TerminalGPT` / better: `tom-doerr/vim-ai`
**Actual target:** `tom-doerr/vim-ai`
**GitHub:** https://github.com/tom-doerr/vim-ai
**Category:** Editor extension with explicit action seam
**Stars:** ~3k | **License:** MIT | **Active:** 2024-2025

**Why it survived:** `vim-ai` exposes Vim commands (`:AIEdit`, `:AIComplete`, `:AINewTextWindow`) that produce durable text mutations in an open file. These are explicit, reversible, governable actions. There is no autonomous agent loop. The extension is a thin Vim plugin; Orket can be the BFF that intercepts AI requests before they reach the model and after the edit is applied.

**Governed action seam:** Each `:AIEdit` call is an `intended_target_ref = buffer_path:line_range` with an `observed_result_ref = new_content_hash`. The `before_tool` interceptor validates the edit scope (no forbidden files, no deletion-only edits) before the LLM call is routed.

**Architecture fit:** ✅ Current — Orket can be wired as the OpenAI-compat endpoint the plugin calls. The BFF layer intercepts the HTTP request, injects governance, and passes through to the local model.

**Main integration risk:** Vim's synchronous plugin model means Orket's async approval path cannot pause execution waiting for human approval without blocking the editor. This limits approval gating to pre-validation only, not interactive approval.

---

### #3 — `nickel-lang/nickel`
**GitHub:** https://github.com/nickel-lang/nickel
**Category:** Configuration language / policy DSL
**Stars:** ~2.5k | **License:** MIT | **Active:** 2025

**Why it survived:** Nickel is a typed configuration language used to generate JSON/YAML configuration for deployment systems. Configuration generation is a governed action — the output is a durable artifact that configures real infrastructure. Orket can govern which Nickel contracts are valid, validate the output against policy, and record the configuration snapshot as part of `publish_run_snapshots()`.

**Governed action seam:** Each evaluation of a Nickel expression is a `ToolCall(tool="evaluate_nickel_contract", args={contract_file, input_params})`. The output is a `ResolvedConfigurationSnapshot`. The `ToolGate` validates that the contract is on the approved list before evaluation.

**Architecture fit:** ✅ Current — `OpenClawJsonlSubprocessAdapter` wraps the `nickel` CLI binary. No autonomous agent loop in Nickel itself.

**Main integration risk:** Nickel evaluation can be side-effect-free (pure functions) or can import external data (contracts that call into JSON files). The governance boundary must distinguish pure evaluations from data-importing ones.

---

### #4 — `Exafunction/codeium.vim` / better: `zed-industries/zed` extension API
**Actual target:** `zed-industries/extensions` (the Zed extension protocol)
**GitHub:** https://github.com/zed-industries/extensions
**Category:** Editor extension with WebAssembly sandbox
**Stars:** ~1.5k (extensions repo) | **License:** Apache-2.0 | **Active:** 2025

**Why it survived:** Zed has a published extension protocol using WebAssembly with explicit capability declarations. Extensions must declare what host functions they call. This is exactly the insertion seam Orket needs — the extension manifest declares capabilities, Orket validates them via `CapabilityRegistry`, and the WASM sandbox enforces them at runtime (unlike Orket's own extension sandbox which is import-scan-only). The Zed extension API has explicit action types: language server calls, code actions, diagnostics.

**Governed action seam:** Code actions (refactor, rename, insert snippet) map directly to `ToolCall` records with `intended_target_ref = file:line`. Orket's `TurnLifecycleInterceptor.before_tool` hooks into the code action pipeline.

**Architecture fit:** ⚠️ Future — Orket needs to be able to declare a WASM-compatible capability provider, which requires the `CapabilityRegistry` to support non-Python backends. The extension protocol itself is a good fit, but wiring requires a new capability adapter.

**Main integration risk:** Zed's WASM sandbox and Orket's Python runtime are different execution models. The adapter is a native host function bridge, not a subprocess adapter. Medium-to-large engineering effort.

---

### #5 — `simonw/datasette`
**GitHub:** https://github.com/simonw/datasette
**Category:** Read/write data API with plugin system
**Stars:** ~9.5k | **License:** Apache-2.0 | **Active:** 2025

**Why it survived:** Datasette exposes a plugin system and HTTP API over SQLite databases. Its `write` API (via `datasette-write`) is an explicit governed action surface: `INSERT`, `UPDATE`, `DELETE` on named tables. These are durable mutations with a clear authorization model. Datasette has no AI agent loop of its own — it is a governed data layer. Orket wraps it via the BFF: all write operations are routed through Orket before reaching Datasette.

**Governed action seam:** Each HTTP `POST/PUT/DELETE` to Datasette's write API is a `ToolCall(tool="datasette_write", args={table, operation, row})` with an `EffectJournalEntryRecord`. Approval gating can pause before the write is committed.

**Architecture fit:** ✅ Current — BFF intercepts HTTP, validates via `ToolGate`, journals the mutation. No new contracts needed.

**Main integration risk:** Datasette's plugin ecosystem can bypass the BFF by calling the underlying SQLite directly. Governance is only at the HTTP boundary, not the database level.

---

## Ranked 25 — Full List

| Rank | Repo | URL | License | Stars | Category | Fit | Effort | Rec |
|------|------|-----|---------|-------|----------|-----|--------|-----|
| 1 | files-to-prompt | github.com/simonw/files-to-prompt | Apache-2.0 | ~2.4k | CLI/file | ✅ Current | Small | Pursue |
| 2 | vim-ai | github.com/tom-doerr/vim-ai | MIT | ~3k | Editor | ✅ Current | Small | Pursue |
| 3 | nickel-lang/nickel | github.com/nickel-lang/nickel | MIT | ~2.5k | Config DSL | ✅ Current | Medium | Pursue |
| 4 | zed-industries/extensions | github.com/zed-industries/extensions | Apache-2.0 | ~1.5k | Editor ext | ⚠️ Future | Large | Maybe |
| 5 | simonw/datasette | github.com/simonw/datasette | Apache-2.0 | ~9.5k | Data API | ✅ Current | Medium | Pursue |
| 6 | httpie/cli | github.com/httpie/cli | BSD-3 | ~33k | CLI/HTTP | ✅ Current | Small | Pursue |
| 7 | jroimartin/gocui → charmbracelet/bubbletea | github.com/charmbracelet/bubbletea | MIT | ~28k | TUI | ✅ Current | Medium | Maybe |
| 8 | casey/just | github.com/casey/just | MIT-0 | ~22k | Task runner | ✅ Current | Small | Pursue |
| 9 | nicowillis → rhasspy/piper | github.com/rhasspy/piper | MIT | ~7k | Voice TTS | ✅ Current | Small | Pursue |
| 10 | openai/whisper | github.com/openai/whisper | MIT | ~75k | Voice STT | ✅ Current | Small | Pursue |
| 11 | playwright-community/playwright-python | github.com/microsoft/playwright-python | Apache-2.0 | ~11k | Browser | ⚠️ Future | Medium | Maybe |
| 12 | nickel-lang/organist | github.com/nickel-lang/organist | MIT | ~200 | Infra automation | ✅ Current | Medium | Maybe |
| 13 | helix-editor/helix | github.com/helix-editor/helix | MPL-2.0 | ~35k | Editor | ⚠️ Future | Large | Maybe |
| 14 | sigoden/argc | github.com/sigoden/argc | MIT | ~700 | Shell cmd framework | ✅ Current | Small | Pursue |
| 15 | BurntSushi/ripgrep | github.com/BurntSushi/ripgrep | MIT/Unlicense | ~50k | Search CLI | ✅ Current | Small | Maybe |
| 16 | coder/coder | github.com/coder/coder | AGPL-3.0 | ~9k | Dev environment | ⚠️ Future | X-Large | Maybe |
| 17 | anchore/syft | github.com/anchore/syft | Apache-2.0 | ~6k | SBOM/scanning | ✅ Current | Medium | Maybe |
| 18 | oxsecurity/megalinter | github.com/oxsecurity/megalinter | AGPL-3.0 | ~3.5k | Lint runner | ✅ Current | Medium | Maybe |
| 19 | astral-sh/ruff | github.com/astral-sh/ruff | MIT | ~35k | Linter/fixer | ✅ Current | Small | Maybe |
| 20 | ko-build/ko | github.com/ko-build/ko | Apache-2.0 | ~7.5k | Container build | ⚠️ Future | Large | Maybe |
| 21 | containerd/nerdctl | github.com/containerd/nerdctl | Apache-2.0 | ~8k | Container CLI | ⚠️ Future | X-Large | Reject |
| 22 | dagger/dagger | github.com/dagger/dagger | Apache-2.0 | ~12k | Pipeline engine | ❌ Engine | X-Large | Reject |
| 23 | nickel-lang → dhall-lang/dhall-haskell | github.com/dhall-lang/dhall-haskell | BSD-3 | ~4.3k | Config lang | ✅ Current | Medium | Maybe |
| 24 | JanDeDobbeleer/oh-my-posh | github.com/JanDeDobbeleer/oh-my-posh | MIT | ~17k | Shell prompt | ❌ No actions | N/A | Reject |
| 25 | nvim-neorg/neorg | github.com/nvim-neorg/neorg | GPL-3.0 | ~7k | Note system | ✅ Current | Medium | Maybe |

---

## Full Entries — Top 10 with Detail

---

### #6 — `httpie/cli`
**GitHub:** https://github.com/httpie/cli
**Category:** HTTP client CLI
**Fit:** ✅ Current | **Effort:** Small | **Rec:** Pursue

HTTPie is a thin CLI that makes HTTP requests. Every invocation is a bounded action: `METHOD URL [headers] [body]`. Orket wraps it via `OpenClawJsonlSubprocessAdapter` and records each request as a `ToolCall` with `intended_target_ref = URL` and `observed_result_ref = response_hash`. The `ToolGate` validates the target URL against an allowlist before the request fires. The governance value is clear: no AI system should make arbitrary HTTP calls without a durable record. Httpie has no competing agent loop; it is a pure command dispatcher. Integration risk: HTTPie sessions (cookies, redirects) produce state that is not naturally captured in the JSONL protocol — multi-step HTTP flows need a session-level record.

---

### #7 — `charmbracelet/bubbletea`
**GitHub:** https://github.com/charmbracelet/bubbletea
**Category:** TUI framework
**Fit:** ✅ Current | **Effort:** Medium | **Rec:** Maybe

Bubbletea's `Model` / `Update` / `View` loop is a clean functional state machine. An Orket extension that wraps a Bubbletea application can intercept messages via the `Msg` type — every user action that causes a state transition is a governed event. The `ScreenRenderer` capability in the SDK (`orket_extension_sdk/tui.py`) provides a `Panel` protocol that maps directly to Bubbletea's `View()` output. The insertion seam is the `Update()` function: Orket intercepts the `Msg`, validates it via `ToolGate`, records it, and passes it through. This is a medium effort because the Go/Python boundary requires a subprocess bridge. Integration risk: Bubbletea's event loop runs in Go; the JSONL adapter must bridge Go ↔ Python. Event ordering guarantees must be preserved.

---

### #8 — `casey/just`
**GitHub:** https://github.com/casey/just
**Category:** Task runner (Makefile alternative)
**Fit:** ✅ Current | **Effort:** Small | **Rec:** Pursue

`just` executes named recipes from a `justfile`. Each `just recipe-name` call is an explicit named action with known inputs and predictable side effects. This is the cleanest insertion seam: Orket wraps `just` via `OpenClawJsonlSubprocessAdapter`, the `ToolGate` validates which recipes are allowed (and with which args), and the effect journal records which recipe ran, when, with what exit code. Recipes are durable mutations (build, deploy, migrate-db). Orket adds exactly what `just` lacks: approval gating before dangerous recipes, a replay record of what ran, and a `failed/unknown/completed` outcome classification when a recipe exits non-zero. Integration risk: `just` recipes can call arbitrary shell; the governance boundary is at recipe invocation, not at the shell command level.

---

### #9 — `rhasspy/piper`
**GitHub:** https://github.com/rhasspy/piper
**Category:** Local voice TTS
**Fit:** ✅ Current | **Effort:** Small | **Rec:** Pursue

Piper is a fast local TTS engine (ONNX-based, no cloud dependency). It maps exactly to `orket_extension_sdk.audio.TTSProvider`. The `synthesize(text, voice_id)` protocol is already defined in the SDK. Wrapping Piper as a `TTSProvider` is the integration. Governance value: every voice output is a committed statement with a recorded text input, voice model ID, and timestamp. In agentic voice systems, what was said matters as much as what was done. Integration risk: Piper is a binary subprocess, not a Python library. The audio output (PCM bytes) must be streamed or buffered efficiently. The `AudioClip.samples: bytes` field in the SDK handles this.

---

### #10 — `openai/whisper`
**GitHub:** https://github.com/openai/whisper
**Category:** Voice STT (local inference)
**Fit:** ✅ Current | **Effort:** Small | **Rec:** Pursue

Whisper maps exactly to `orket_extension_sdk.voice.STTProvider`. The `transcribe(request: TranscribeRequest) -> TranscribeResponse` protocol is defined. Wrapping Whisper as an `STTProvider` closes the voice input loop. Every voice-to-text transcription is a durable input record: what was said, when, with what confidence, from which audio source. This matters for governed voice-action systems where a misheard command executing a destructive action is a liability. Note: Whisper is fine to use via the `openai` Python package (open-weight models run locally). The package is not closed-core. Integration risk: Whisper inference is slow on CPU; GPU is needed for production use. The `STTProvider` protocol is synchronous — blocking GPU calls on the main thread will stall the event loop.

---

### #11 — `microsoft/playwright-python`
**GitHub:** https://github.com/microsoft/playwright-python
**Category:** Browser automation
**Fit:** ⚠️ Future | **Effort:** Medium | **Rec:** Maybe

Playwright's Python bindings expose every browser action (`click`, `fill`, `goto`, `screenshot`, `evaluate`) as explicit Python function calls. These are the most concrete governed actions possible — durable mutations to web state. The `ToolGate` can validate actions against an allowlist (permitted URLs, permitted form fields). Each action is an `EffectJournalEntryRecord`. The future contract requirement: Orket currently has no approval surface that can pause mid-sequence and wait for human confirmation before a destructive click (e.g., "submit payment"). The `before_tool` hook can block, but cannot pause-and-resume. This is a ⚠️ Future fit because the approval-pause-resume contract needs to exist before Playwright's most powerful use cases are governable. Integration risk: Playwright sessions have stateful page context; the JSONL adapter's stateless request model doesn't naturally capture multi-step browser sessions.

---

### #14 — `sigoden/argc`
**GitHub:** https://github.com/sigoden/argc
**Category:** Shell command framework / argument parser
**Fit:** ✅ Current | **Effort:** Small | **Rec:** Pursue

`argc` is a Bash-based command framework that turns annotated shell scripts into documented CLIs with argument validation. It is thinner than `just` but has the same governance seam: named commands with declared arguments. Orket wraps `argc` commands via `OpenClawJsonlSubprocessAdapter`. Each command invocation is a `ToolCall` with declared argument schema (from `argc`'s annotations) that the `ToolGate` can validate before execution. This is a rare case where the target has its own argument schema — the ToolGate doesn't need to infer schema from convention. Integration risk: `argc` targets are Bash scripts, which can call arbitrary shell. Same boundary issue as `just`.

---

### #17 — `anchore/syft`
**GitHub:** https://github.com/anchore/syft
**Category:** SBOM generation / container scanning
**Fit:** ✅ Current | **Effort:** Medium | **Rec:** Maybe

Syft generates Software Bill of Materials (SBOM) for container images and filesystems. It is a CLI tool with a structured JSON output. In governed software supply chain workflows, SBOM generation is an explicit attested action: "at time T, this image contained these packages." Orket wraps `syft` via `OpenClawJsonlSubprocessAdapter`, records the invocation as an `EffectJournalEntryRecord`, and captures the SBOM as a `ResolvedConfigurationSnapshot`. The governance value: an AI system that builds and deploys images without attested SBOM records is ungovernable. Integration risk: Syft scans are read-only (no mutations) so the effect journal records intent and observation, not a state mutation. This is a lighter governance use case.

---

### #18 — `oxsecurity/megalinter`
**GitHub:** https://github.com/oxsecurity/megalinter
**Category:** Linter orchestrator
**Fit:** ✅ Current | **Effort:** Medium | **Rec:** Maybe

MegaLinter runs 50+ linters in Docker and produces a structured report. Each linter invocation is an explicit scan with a known target, tool version, and result. Orket wraps MegaLinter's `REPORT_OUTPUT_FOLDER/megalinter-report.json` as a post-run `WorkloadResult`. The governance value: in an AI-assisted code workflow, whether lint passed or failed is a durable fact that should be recorded alongside the code change, not just printed to stdout. The `ToolGate` validates which linters are enabled before the run. Integration risk: MegaLinter is a Docker-first tool; the subprocess adapter must be a Docker wrapper, not a direct binary call.

---

### #25 — `nvim-neorg/neorg`
**GitHub:** https://github.com/nvim-neorg/neorg
**Category:** Structured note/task system (Neovim plugin)
**Fit:** ✅ Current | **Effort:** Medium | **Rec:** Maybe

Neorg is a Neovim plugin for structured notes, tasks, and journals in a custom `.norg` format. It has explicit action commands: create note, add task, change task status (`todo`/`doing`/`done`/`cancelled`). Task status transitions are governed actions — the same state machine vocabulary as Orket's `CardStatus`. An Orket adapter that wraps Neorg's task API would record every task creation, status change, and completion as an `EffectJournalEntryRecord`. The governance value is small-to-medium (note-taking is lower stakes than infrastructure), but the structural fit is excellent and the adapter would be thin. Integration risk: Neorg is Lua-based and Neovim-only. The adapter must communicate via Neovim's RPC protocol, which requires a lightweight RPC bridge not currently in Orket's adapter suite.

---

## Rejection Summary

**Removed from the original 100 for these reasons:**

**Chatbox / LLM frontend (largest group, ~30 rejections):** Any repo whose primary interface is a chat window, prompt panel, or "talk to your data" UI. These have no action seam — they are the UI, not the governed layer beneath it. Examples: Open WebUI, LobeChat, LibreChat, Jan, GPT4All (UI mode).

**Engine-heavy / already is the orchestrator (~20 rejections):** Repos that are themselves agentic runtimes, workflow orchestrators, or planning engines. Adding Orket would mean replacing their execution model, not wrapping it. Examples: LangGraph, CrewAI, AutoGen, AgentScope, MetaGPT, Agen, OpenHands, SWE-agent. These are Orket's peers, not Orket's substrates.

**Stale / abandoned (~15 rejections):** No commits in 12+ months, or maintained only with dependency bumps. Governance infrastructure for a dead project is wasted. Examples: Various "GPT + X" repos from 2023.

**Closed-core dependency (~10 rejections):** Projects whose main value requires a proprietary API, closed model, or licensed dataset at the center. Examples: Any repo that is functionally a thin wrapper over a specific closed model API.

**No explicit action boundary (~10 rejections):** Projects with "AI assistant" behavior but no discrete, enumerable action types. Orket needs a tool name and args — if the target is just "respond to user input" with no action taxonomy, there is nothing to gate.

**Would require engine surgery (~5 rejections):** Projects that have their own tool dispatch, execution loop, or action planner that would need to be replaced rather than wrapped. Dagger is the clearest example: Dagger *is* a governed pipeline engine and integrating Orket would mean one engine trying to govern the other.
