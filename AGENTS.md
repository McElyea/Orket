# Agent Instructions

## Response Formatting
1. When referencing files, use plain backticked paths only (for example: `docs/ROADMAP.md`).

## CI Failure Delta Check (Required Each Run)
Before any implementation work, the agent must perform a CI failure delta check against Gitea and update local records.

### Inputs
1. Previous snapshot: `.orket/durable/ci/last_state.json` (if missing, treat as first run).
2. Current Gitea workflow failure state (failed runs/jobs/steps).

### Required Processing
1. Compare current state to previous snapshot.
2. Classify failures:
   - `P0`: required gate failing on `main`
   - `P1`: failing PR gate
   - `P2`: scheduled/non-blocking failure
3. Build delta sets:
   - `new_failures`
   - `still_failing`
   - `resolved_since_last_run`

### Required Outputs (Every Run)
1. Human report: `benchmarks/results/ci_failure_dump.md`
   - Summary counts by priority (`P0/P1/P2`)
   - Prioritized list
   - Full raw failure dump for analysis
2. Machine snapshot: `.orket/durable/ci/last_state.json`
   - Current normalized failure state used as next-run baseline
3. Raw dump: `benchmarks/results/ci_failure_dump.json`
   - Full normalized run/job/step failure payload

### Alert Rule
1. Emit `BAD_GATE_ALERT` if any `P0` exists.
2. Emit `STALE_FAILURE_ALERT` if the same failure remains unresolved for 3 consecutive runs.

### Execution Rule
1. If `P0` exists, the agent must report it first before continuing task work.
2. The agent may continue non-release work after reporting, but must not hide or skip `P0`.
3. Preferred command:
   - `python scripts/ci/ci_failure_delta.py`
4. Docs hygiene auto-remediation:
   - If failures are in docs project hygiene or contract-path checks, the agent must auto-fix in the same run.
   - Required fix flow: archive/move/update references, rerun the failing checks, then report outcomes.
   - Preferred checks:
     - `python scripts/check_docs_project_hygiene.py`
     - `python -m pytest tests/contracts/test_workload_contract_schema.py -q`

## Live Integration Verification (Required)
For any new or changed integration/automation (CI, APIs, webhooks, runners, external services), the agent must verify behavior with a live run against the real configured system before declaring completion.

### Required Proof
1. Run the real command/flow end-to-end (not compile-only or dry-run-only).
2. Record observed mode/path and result (for example: primary API path vs fallback path).
3. If live run fails, capture exact failing step/error and either fix it or report the concrete blocker.

### Testing Policy Reference
1. `docs/TESTING_POLICY.md` remains the canonical test lane/gate reference.
2. `AGENTS.md` defines execution discipline (including required live verification).
