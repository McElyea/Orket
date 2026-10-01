# ATG-05 named E2 hotspot closeout

Date: 2026-10-01 (America/Denver)
Status: Source exit passed; annotated v0.6.122 publication pending
Owner: Orket Core

## What changed

Finish the three frozen roots without expanding the size audit. Orchestrator ops
moves context/history construction to a concrete module; both function ASTs are
unchanged. ToolDispatcher keeps its loop/exception/completion boundary and delegates
existing checks and result operations to focused functions, with data records for
existing invocation values and progress. Effect attributes remain selected at their
original use points. MessageBuilder retains capture, first observation, stage order,
read/notice waits and compaction while contract/section/requirements modules retain
its existing prompt rendering. No compatibility proxy or extra lifetime owner.

| Root | Before | After | Largest final function |
|---|---:|---:|---:|
| orchestrator_ops.py | 478 | 397 | 67 |
| turn_tool_dispatcher.py | 635 | 187 | 69 |
| turn_message_builder.py | 490 | 81 | 48 |

All seven new modules are <=400 lines with functions <=70; their data classes
expose no new public behavior methods. The adjacent orchestrator remains 361 lines
with its pre-existing 73-line constructor unchanged. That constructor is outside
the three named roots. No claim of repository-wide size conformance is made.

## What was verified

Live Windows Python 3.11 source proof: opening/closing batches pass the same
105, 148 and 108 cases. The combined run has **538 passed / 1 failed**, one upstream
Starlette deprecation warning. The sole failure was a newly grouped workflow
observer requiring two prompt checks in one command; the existing jobs each run
both in separate commands. Correcting the observer to require each check per job
passes all **30 workflow cases**. Unchanged runtime proof plus that scoped recheck
covers all **539 distinct selected cases**; this is not a single zero-exit combined
run, nor 568 distinct passes. Every campaign retains unchanged source inputs.

Real file/SQLite effects, cards/checkpoints, protocol/replay receipts, input
mutation, required read/notice publication, cancellation/timeout/native settlement,
provider preparation/HTTP cleanup, approval continuation and control-plane final
truth retain their existing checks. Supplied model/provider controls are not live
llama.cpp inference. Two contract event observers now instrument the extracted
event owners; their assertions and layer labels remain. Prompt inventory now scans
all extracted renderers. Existing assertions, deadlines and skips are unchanged.
Observed healthy path: primary/success. Adverse controls observe the expected
failure, refusal or partial effect; no new fallback path is introduced.

Structural proof passes Ruff, dependency direction (1,222 sources / 4,256 edges;
zero violations, cycles or analysis errors), strict taxonomy (12,123 collected),
critical no-op, docs hygiene, authority structure/generated equality and release
policy. Both Quality job declarations retain the affected controls. Hosted jobs
were not executed. Final Ruff passes after the guard-only correction; relevant
unchanged structural evidence is reused. The receipt binds commands, source/log
hashes, exact file list and scope. Local process records are `.tmp/atg05-proof.json`
and `.tmp/atg05-structural.json`.

## What was not verified

No refreshed canonical Mypy or complete 89-percent coverage run; those are ATG-06/07.
No fresh installed Windows/Linux, live llama.cpp inference or hosted Gitea Quality
acceptance. Structural size/AST evidence does not replace runtime proof. Broader
C/D/E acceptance, every oversized file and main merge are excluded.

## Remaining blockers or drift

Typing and coverage remain red. Provider/hosted access and current Linux clock
acceptance remain unestablished. The earlier deferred marshaller process teardown
finding remains outside this queue. The authority checker still proves structure,
not general current runtime conformance. None blocks eligible local ATG-06 work.

## Exact files touched

The full list is in `VERIFICATION.json`: eleven production files, two affected
contract observers, Quality workflow/guard, architecture/contributor documentation,
queue/worksets, ATG-04 publication readback, closeout and version metadata.
