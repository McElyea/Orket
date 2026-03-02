# Agent Instructions

## Response Formatting
When referencing files, use plain backticked paths only (for example: `docs/ROADMAP.md`).

## Live Integration Verification (Required)
For any new or changed integration/automation (CI, APIs, webhooks, runners, external services), the agent must verify behavior with a live run against the real configured system before declaring completion.

### Required Proof
1. Run the real command/flow end-to-end (not compile-only or dry-run-only).
2. Record observed mode/path and result (for example: primary API path vs fallback path).
3. If live run fails, capture exact failing step/error and either fix it or report the concrete blocker.

### Testing Policy Reference
1. `docs/TESTING_POLICY.md` remains the canonical test lane/gate reference.
2. `AGENTS.md` defines execution discipline (including required live verification).
