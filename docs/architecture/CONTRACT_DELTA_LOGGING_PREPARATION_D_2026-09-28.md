# Explicit logging preparation and operation context

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; corrected focused source controls pass; full current/platform acceptance pending.
- Contracts: `LOG_WRITE_SETTLEMENT.md`, `API_RUNTIME_LIFECYCLE.md`.

## Delta

Cold optional logging formerly started its writer and captured relative cwd on
the loop. Two unchanged-product controls reproduced blocked sibling SQLite work;
two native counterparts passed. The existing writer now prepares natively from
explicit immutable application inputs. Loop logging requires a prepared binding.
One queue, daemon, failure latch and subscriber owner remain process-global.

Canonical composition supplies operation-local bindings. Borrowed lifespan yields
do not retain ContextVar tokens across caller tasks. API/webhook request owners
bind admitted work; refused ASGI sends use the restored caller. CLI setup owns its
same-task command context. Interfaces use application services without new adapter
imports. The shared request/cleanup and native-I/O algorithms remain authoritative.

## Migration Plan

1. Direct async logging callers prepare `LoggingInputs` and bind the returned
   value in their actual operation task. Canonical owners perform this setup.
2. Direct container and constructor-bypassing fixtures supply explicit prepared
   values. No global autouse preparation or fallback conceals missing ownership.
3. Retain real startup fault/cancellation, process exit, independent SQLite,
   physical records, task-context, existing queue/frontier and owner controls in
   both Quality jobs. The daemon remains process-owned through partial start;
   application cleanup does not claim to stop or join it.
4. Nineteen separately inventoried required producers and their finalizers remain
   open. This preparation change does not complete D, coverage or platform gates.

## Verification

The prior public-path opening passed two native cases and failed two loop cases
in 8.11s. It retained 5,531 source inputs and three scratch probe/controller inputs;
all twelve recorded process identities were absent after owner cleanup. Evidence:
`.tmp/goal-20260928-logging-preparation-opening-v2-*`. This records the original
failure, not current corrected behavior. Subsequent source results follow.

The first combined 43-selector source closing reports **386 passed, 6 failed** in
178.61s, 5,558 unchanged inputs. All 34 native writer-start controls, eight borrowed
task-context controls and ten request/CLI context controls pass. Failures expose
two outdated class-to-function constructor hooks, three unit patches aimed at old
log bindings and one direct ToolBox fixture lacking logging admission. Consumer
correction and rerun are required; the original report remains at
`.tmp/goal-20260928-logging-preparation-closing-v3-*`.

Canonical Ruff initially refused ten import blocks that scratch classification
had accepted. Root applied canonical import sorting; subsequent Ruff passes.
Mypy exposed three new declaration errors. Literal overloads now describe required
selection accurately and the dispatch mixin declares its actual prepared-context
field under TYPE_CHECKING. Implementation bodies remain structurally equal;
import-order equality is not claimed. Receipt:
`.tmp/d-logging-combined-20260928/root-corrections.json`.

The initial native gates bind 5,558 unchanged inputs: Ruff, dependency, no-op,
strict taxonomy, authority, hygiene and diff checks pass; Mypy fails at 655 errors
in 194 files before those three declaration corrections. Dependency observes
1,208 files/4,100 edges/six dynamic routes without violations/errors. Taxonomy
collects 11,111 correctly classified items. Authority remains structural only,
with current runtime proof unavailable. Evidence: `.tmp/goal-20260928-post-logging-native-*`.

Three reviewed scratch drafts are combined in `.tmp/d-logging-combined-20260928/`.
The assembly checks original source baselines and candidate hashes before writing
49 paths, including two later scope/layer corrections. Original drafts remain
immutable. Its shared owner explicitly rebases to the accepted nested-fatal and
typing corrections; earlier static receipts do not stand in for current runtime
proof. Structural review preserves the original writer and request algorithms.


The six-path extra-consumer and four-path fixture supplements were applied only
after checking all baselines. Before the audit correction, its two existing real
integration cases failed with `E_LOGGING_PREPARATION_REQUIRED` (0.50s, 5,562
unchanged inputs). The audit now prepares/binds before collection and supplies
its direct harness; this adds an earlier failure boundary. Existing final frontier,
temporary workspace cleanup and exact primary/secondary precedence remain.
Thirteen CLI fixture patches now target the actual extension-command binding.

The 59-selector combined closing reports **603 passed, 2 failed** in 198.28s,
all 5,562 inputs unchanged, with one upstream warning. All 41 previously observed
consumer failures, audit controls and 60 workspace controls pass. The two failures
are the organization test's remaining consumer of the constructor hook changed
by the supplement. Root corrected that one hook to the genuine class initializer;
all **11** organization/runtime-factory cases then pass in 1.77s, with unchanged
inputs. Existing assertions and actual held construction/cleanup remain. This
does not relabel the 603/2 campaign as wholly passing. Evidence:
`.tmp/goal-20260928-audit-logging-opening-v1-*`,
`.tmp/goal-20260928-logging-workspace-closing-v4-*`, and
`.tmp/goal-20260928-logging-organization-repair-v5-*`.

Proof is live local native/files/SQLite/process and application routes plus
declared contract/unit controls, path primary. The integrated campaign is partial
success; its remaining corrected controls pass. Fresh installed-wheel, Linux,
full current suite and required-producer acceptance remain absent.

## Rollback Plan

Drain admitted operations before restoring source, direct consumers and contracts
together. Retain failure receipts and process ownership; no queue restart or effect
rollback follows from reverting preparation.

## Versioning Decision

Unreleased 0.6.114 source correction; no version bump. Direct async embeddings
must migrate to explicit preparation. Existing queue/frontier and process-lifetime
limits remain, including possible daemon survival after a partial start failure.


The later Python 3.12.2 current-source campaign passes all **605** combined cases
in 216.87s, 5,569 unchanged inputs, one upstream warning. All identities match
the earlier 3.11 combined campaign; its two corrected cases passed separately.
All 1,228 product files match across those campaigns and all 4,956 historical
installed bindings remain intact. Comparison:
`.tmp/goal-20260928-logging-workspace-parity.json`. This is scoped source success;
the original 603/2 result remains unchanged. No fresh installed or Linux claim.


### Further direct turn consumers

Terminal seed/replay opening fails all 26 cases. Five composed/native turn groups
fail 27 representative cases while the logger-unreachable pre-owner cancellation
guard passes. Cached dispatch opening fails all 11 selected cases. Explicit
preparation/binding now occurs only in the actual executing task at reviewed
logger-reachable calls; lower leaf/replay exclusions stay scoped to their actual
paths. All 103 full group/isolated-context cases pass inside the 330-case closing.
The three patches preserve 131, 172 and 130 original assertion ASTs respectively;
overlapping files apply in declared prerequisite order. No global fixture binding,
fake logger or publication-authority change is introduced. Evidence:
`.tmp/goal-20260928-trust-score-consumers-opening-v1-*`,
`.tmp/goal-20260928-cached-dispatch-opening-v1-*` and the closing below.
Broader ordinary TurnExecutor/control-plane consumers remain separate work.

## Observed source closing

All **330** selected Windows Python 3.11 source cases pass in 56.20s, with
**5,612 unchanged Git-visible inputs** and one upstream Starlette warning.
This includes all 27 trust-handoff and 14 score-root controls, retained kernel/API,
model-policy and ledger-order guards, direct logging consumers, typing regressions
and 30 workflow-gate checks. Evidence:
`.tmp/goal-20260928-trust-score-consumers-closing-v1-{inputs,readback}.json` and
sibling XML/log. Proof is live local native/files/SQLite/CLI behavior plus declared
contract/structural controls, path primary, result success. Current installed,
Linux, actual model inference and complete D/E acceptance remain separate.


### Direct TurnExecutor control-plane consumers

Four further integration modules add 31 local prepare/bind scopes in their actual
executing tasks, preserving all 336 assertion ASTs and original retained-state
checks. The five direct preflight/store/publication controls stay unbound. The
opening observes **38 failed, five passed**; all **43 closing cases pass** in 7.61s
with 5,616 unchanged inputs. Proof uses real SQLite and terminal file effects with
declared supplied model/tool ports; optional setup grants no drain or completion
authority. Evidence: `.tmp/goal-20260928-turn-control-logging-{opening,closing}-v1-*`.
Broader application context/middleware/skill and remaining direct consumers stay
separate pending groups; no general caller migration or provider claim follows.


### Remaining reviewed direct TurnExecutor consumers

The three application modules now pass all 60 checks after a representative
opening with 19 preparation failures and one lower-level pass. Twelve remaining
modules pass all 90 checks after a 29-case opening with 26 preparation failures
and three passes. Operation-local bindings preserve all 254 and 178 original
assertions, respectively. Healthy completed-card replay prepares logging; damaged
receipt reentry remains unbound and refuses from retained state. Lower-level and
pre-prompt short-circuit controls retain their deliberate exclusions.

This completes the bounded literal/direct and reviewed helper-routed TurnExecutor
test-consumer inventory. It is not a whole-program logger reachability proof.
Real local artifact/SQLite/native-process checks and declared supplied-port cases
pass (primary, success); actual provider and fresh installed proof are separate.
Evidence: `.tmp/goal-20260928-turn-application-artifact-import-opening-v1-*`,
`.tmp/goal-20260928-roots-remaining-opening-app-imports-closing-v1-*` and
`.tmp/goal-20260928-roots-remaining-epic-closing-v1-*`.
