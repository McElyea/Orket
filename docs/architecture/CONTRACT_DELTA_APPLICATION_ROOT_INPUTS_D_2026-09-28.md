# Application validation and reconciliation root inputs

Date: 2026-09-28
Status: Bounded D1 correction implemented; Windows source proof passes, installed proof pending

## Scope and identified gap

The pure ToolGate and structural reconciliation policies already consume explicit
facts/assets. The narrower application defect concerns when their existing native
owners select filesystem roots. ToolGate retained a relative workspace and read
its attribute again in the validation worker. Structural reconciliation selected
default model/workspace roots in separate workers, and the store resolved a
relative root again during snapshot and apply. A changed CWD could select a
different matching tree between those operations. Canonical callers supplying
absolute roots avoid that particular CWD ambiguity; direct relative-root callers
remain reachable. These are source findings, not reported opening observations.

## Root handoff

ToolGate captures its workspace through the existing `capture_file_roots` before
waiting for file facts. The worker receives that Path explicitly for joining,
native resolution/containment and iDesign validation. The current argument/role
and selected-context capture, AST checks, core policy ordering and validation
messages remain. Capture errors in the existing OSError/ValueError/TypeError
family become the existing `Invalid file path:` facts error. A missing path or
another tool operation does not acquire a filesystem-root requirement.

StructuralReconciler captures both configured root selectors together before its
outer owned operation waits. Missing roots use the captured invocation project
base. The existing `project_paths.default_model_root` and
`default_workspace_root` functions remain the sole default-layout authority and
run in their existing native owners with that explicit base. The application does
not reproduce `model` or `workspace/default` layout rules. Later CWD or owner
attribute changes cannot retarget an already admitted reconciliation.

StructuralBoardStore binds a relative root at constructor entry so ordinary
snapshot and apply on that instance share the selected project base. Each async
method captures the current stored Path before awaiting and passes it explicitly
to its native worker. This also prevents an attribute change after admission from
retargeting that operation. The store does not freeze arbitrary future assignment
to its public root attribute or introduce a snapshot identity token; deliberate
reconfiguration between completed calls is outside the consistency claim.

All three boundaries reuse `capture_file_roots`. Windows drive-relative roots are
explicitly refused with `E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED` rather than
depending on hidden per-drive current directories. ToolGate reports its existing
invalid-path result; reconciliation/store propagate the input ValueError before
native work. Absolute selections do not acquire an unnecessary CWD observation.
Capture is lexical; resolution, traversal, reads, AST work, comparisons and writes
stay in native workers. Root capture does not bind handles against symlink/path
replacement and introduces no hostile-filesystem confinement guarantee.

## Unchanged policy and effect ownership

The shared I/O owner, cancellation/failure precedence, reconciliation plan and
FileWriteFacts policy are unchanged. Each structural target still compares actual
bytes to its captured expected content, uses the existing temporary-file replace,
verifies readback and only then publishes its adoption event. Earlier writes and
events survive a later target refusal. There is no multi-file transaction, retry,
rollback, provider fallback or new settlement loop. Explicit roots captured by
reconciliation also keep its event destination with the selected tree.

The private ToolGate facts and store snapshot/apply methods gain explicit root
arguments. There are no production outside callers or compatibility exports.
One existing integration hold of the private apply method must pass the root
argument; its operation/assertions/parameters/decorators stay otherwise exact.

## Proposed proof and limits

Eighteen declared integration controls use isolated owned child interpreters so
process CWD changes cannot interfere with other tests. They cover real governed
file effects, real iDesign/AST validation, default and explicit reconciliation,
matching trees through snapshot/apply, direct store construction and attribute
changes, repeated cancellation and real changed-target refusal. The partial
publication case independently reads the first verified write/adoption event,
preserved operator bytes in the second target and untouched other-tree bytes.
Native holds delegate actual operations; they do not supply successful facts,
plans, writes or events. The outer harness verifies origins and child exit/reap.
Windows drive-relative controls skip on other platforms with that explicit reason.

New controls require unchanged-source opening and changed-source closing, followed
by existing pure-policy, application/board and native ownership regressions.
Static AST, file-size and Ruff checks are structural only. Source execution,
installed supported-interpreter proof and current authority integration remain
pending. No provider, sandbox, full board UI behavior, adversarial path replacement
or wider D completion is claimed. The original D1 effect-separation receipt remains
`docs/architecture/CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`; its
historical result ceiling is preserved rather than retroactively rewritten.


### Observed source proof, 2026-09-28

The unchanged-source opening has 17 failures and one passing outside-workspace
refusal. Physical receipts show writes in the later tree and split default
model/event roots; the second-target drift case finishes on the wrong tree instead
of observing the operator edit, so its expected failure slot is absent. Two
drive-relative controls observe the missing refusal. These results remain retained.
All 18 controls and the existing core/application/board/CLI guards pass in the
combined closing recorded by the active plan. Proof is real local file/SQLite,
adoption-event and owned-child execution on Windows Python 3.11 (primary, success).
No whole-core, hostile-filesystem, installed or external-provider acceptance follows.
Evidence: `.tmp/goal-20260928-roots-remaining-opening-app-imports-closing-v1-*`
and `.tmp/goal-20260928-roots-remaining-epic-closing-v1-*`.
