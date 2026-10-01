# Named E2 responsibility extractions

## Summary
- Owner: Orket Core; date: 2026-10-01.
- Scope: ATG-05's three frozen roots only.
- Contracts: `RUNTIME_ARCHITECTURE_POLICY_INPUTS.md`,
  `RUNTIME_EXECUTION_RESULT_CONTRACT.md` and `SHARED_IO_CANCELLATION.md` in `docs/specs/`.

## Delta
Existing context/history construction moves from orchestrator ops into a concrete
context composition workflow, invoked directly by the existing orchestrator methods.
Both moved functions retain identical ASTs. The existing phase callbacks and deferred
policy reads keep their selection timing. No new delegation shim is introduced.

ToolDispatcher keeps its public method, capture call, loop, try/except and final
completion check. Invocation values and counters move into data records; they do
not forward effects. Existing gates/approval and result observation/publication
move into focused functions. Attributes on the selected dispatcher remain read at
the original phase. Continuation refusal, replay isolation, protocol hashing,
receipt order, native ownership, failure identity and partial-effect behavior remain.
Two contract event observers now instrument the concrete event modules.

MessageBuilder keeps captured inputs, first native observation, section ordering,
read/notice waits and final compaction. Pure contract/section formatting and the
existing required-read stages move into three responsibility modules. The literal
prompt-context inventory guard covers all extracted renderers; no capture key or
prompt instruction was dropped. JSON/message order and public methods are unchanged.

Root sizes: orchestrator ops 478 -> 397; dispatcher 635 -> 187; message builder
490 -> 81. Every function in those roots and the seven new modules is <=70 lines;
new modules are <=400 lines and new classes have no public behavior methods.
The existing orchestrator root stays 361 lines; its pre-existing 73-line constructor
is unchanged and outside the named extraction debt. No repository-wide size closure
or whole E2 acceptance is claimed.

## Migration Plan
No public API or serialized migration. Import internal context composition from
its new concrete owner; no compatibility re-export is added. Preserve both Quality
selections' phase, native effect/read, replay and cleanup controls. Opening/closing
source selections pass 105 / 148 / 108 cases; the goal's final combined and structural
proof is recorded in its archive. Installed/platform/provider gates remain later.

## Rollback Plan
Revert only these responsibility extractions if the retained phase/effect/input or
prompt controls disagree. Keep ATG-02/03/04 ownership repairs. Existing partial
files, cards, receipts and approval state retain their existing recovery contracts;
the extraction adds no transaction or rollback mechanism.

## Versioning Decision
Patch checkpoint 0.6.122, effective 2026-10-01. Compatibility preserved;
internal-only audience; no downstream migration requirement. Typing, coverage,
installed Windows/Linux, llama.cpp and hosted acceptance remain open in ATG-v1.
