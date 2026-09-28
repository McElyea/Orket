# Quality checker contract

Status: Active
Owner: Orket Core
Last updated: 2026-09-27

## Scope and source selection

`scripts/governance/enforce_test_taxonomy.py` and
`scripts/governance/check_noop_critical_paths.py` share Git-visible selection through
`scripts/common/git_inventory.py`. Selected roots must exist in one discoverable
Git repository. Existing tracked and nonignored untracked Python files are eligible;
ignored files are not targets. Missing roots, failed Git discovery and empty
collections cannot produce a passing gate. Fixture repositories follow the same
rules. Git-visible selection is inventory admission, not hostile-code isolation.

## Test layer authority

The canonical layers registered in `pyproject.toml` are `unit`, `contract`,
`integration` and `end_to_end`. Each collected pytest item must have exactly one
distinct canonical layer. Duplicate copies of the same marker are harmless;
different inherited or direct layer markers conflict. Module, class, inherited
test-method and parameter-specific markers use pytest's actual collection semantics.
A parameter's marker does not classify other cases. Comments, docstrings, directory
names and live-provider/fixture posture do not supply or override a layer.

The checker collects explicit Git-visible `test_*.py` targets in a fresh interpreter
using `sys.executable`. It runs ordinary pytest collection hooks and imports the
selected tests and their support modules, without executing test bodies. Ambient
`PYTEST_ADDOPTS` and configured `addopts` cannot filter the inventory. Items reported
through pytest's deselection hook remain classified. Custom collection hooks are
trusted repository code; this is not an adversarial collector or import sandbox.

`test_taxonomy_report.v2` counts collected items, including parameter cases, rather
than source function definitions. It preserves missing and conflicting items,
pytest's collection exit status and errors. `--strict` rejects missing or conflicting
layers. Collection/inventory failure and no collected items fail with or without
`--strict`. Non-strict output is an observation, not a taxonomy acceptance verdict.
Baseline summaries preserve the failure fields and disclose truncated item lists.

An `end_to_end` marker is a claim requiring review of the exercised public surface.
The checker cannot establish that claim, actual-provider use, runtime correctness,
coverage, or Quality acceptance from a marker.

## Critical no-op analysis

The default roots remain `orket/application`, `orket/runtime` and `orket/interfaces`.
The checker parses admitted source without importing product modules. Literal-only,
docstring-only, ellipsis, pass, local annotation-only and bare/None-return bodies
are findings, including combinations of those statements. A real operation, returned
value, yielded value or explicit raised failure is not an empty body.

Recognized `typing`/`typing_extensions.TYPE_CHECKING` imports and aliases exclude
only their non-runtime branch; direct negation retains the opposite branch. Genuine
direct Protocol declarations, including parameterized bases, may use declaration
bodies. Explicit None-return defaults remain findings. Imported `abc.abstractmethod`
decorators exempt declarations on recognized ABC/ABCMeta/Protocol classes and their
inspected abstract-capable descendants; similarly named foreign decorators,
ordinary concrete-class and module-level decorated functions do not. Concrete
Protocol implementations and nested executable
functions do not inherit a Protocol exemption.

Rebound or ambiguous inspected bindings cannot justify these exemptions. Python
function/global and class lexical scopes, uncertain branch joins and zero-iteration
loops are treated conservatively. This is bounded static analysis, not a complete
Python control-flow/type evaluator: arbitrary monkeypatching, reflection and imported
code semantics remain outside its proof. No-op absence does not prove useful effects.
Read, encoding and parse failures are failed observations. JSON output requested
with `--out` retains the existing diff-ledger publication behavior.

## Required checks and limits

Quality runs `pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89`.
The explicit configuration path binds the authored branch setting for measured
native Python children even when their working directory differs. Implicit parent
discovery alone can leave child data in statement mode and make combination fail.
Keep native same-directory, lost-configuration and explicit-configuration controls
in both Quality selections. Nested control measurements use their own data files
and discard inherited coverage injection before starting their independent owner.
These controls establish coverage-tool behavior, not application coverage or
hosted Quality acceptance. The coverage floor and test deadlines are unchanged.

The architectural-truth baseline's size observation uses the same Git-visible
Python inventory under `orket/`. Missing or empty inventory, Git discovery, source
read/encoding/parse failure and observed in-scan source changes make collection
fail. The v2 size payload retains the 400-line file and 70-line function thresholds
and complete oversized inventories, alongside the existing largest-25 summaries.
Source hashes bind the observation; counts do not establish runtime defects.

Function spans remain inclusive of nested definitions. Qualified names, enclosing
class/function scopes, direct nested-definition counts and route-decorator syntax
make that overlap visible; spans must not be summed as independent debt. Decorator
spelling is a syntactic observation, not proof of FastAPI binding or an exemption.
Nested router factories and their route functions retain their measured spans.
The complete inventories support later no-growth and shrinking-baseline comparison;
collecting them alone does not establish that a refactor reduced debt.

Run both checker regression modules, the taxonomy-summary regression, the native
checker commands, and canonical `ruff check orket tests`. Migrate classification
by reviewing test behavior; do not add blanket directory labels or weaken coverage
thresholds to obtain green. Repository-wide missing/conflicting layers remain real
gate debt after the checker is repaired. Structural checker success is separate
from runtime proof, full-suite coverage and hosted Quality acceptance.
