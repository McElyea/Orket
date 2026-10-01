# Model-stream workload admission inputs

Date: 2026-09-28
Status: Implemented bounded D input correction; Windows source proof below

`run_model_stream_v1` captures one environment mapping and a deep copy of its
ProviderTurnRequest before target discovery. ProviderTurnRequest's fields and
public schema remain unchanged. This isolates nested request values from caller
mutation during resolution; arbitrary custom objects still retain their existing
Python/Pydantic deep-copy behavior rather than a new JSON-only input schema.

Real-provider preparation uses the existing `capture_process_context` before its
first await and passes that environment/directory into the existing resolver.
Provider identity, requested-model precedence, endpoint defaults, selection/load
flags, model-load timeout and TTL retain their existing resolution helpers and
precedence over the captured mapping. The same snapshot supplies the inference
API key and timeout after resolution. Stub mode does not acquire a CWD requirement.
The core `provider_from_environment` function supplies the same configured-provider
precedence without the old helper's ambient reread.

Turn-timeout parsing also consumes the admission mapping. Its one-second clamp,
invalid-value default and actual wait-for start point are unchanged; time spent in
target preparation is not newly charged to that turn deadline. The deadline,
cancel watcher, provider iterator consumption, event schema/mapping, existing
fallback behavior, error hints and commit intents retain their existing algorithms.
This correction does not introduce a native work owner or change exception
precedence after provider execution starts. Request copying and scalar timeout
conversion now occur before target resolution, which can change when a refusing
custom input is observed; no arbitrary-object side-effect equivalence is promised.

Seven integration controls enter the public builtin workload with a real
InteractionManager, loopback HTTP catalog/completion endpoints and durable commit
readback. They cover nested request mutation, API-key mutation, late inference and
turn budgets, actual relative GGUF selection after a controlled resolver-entry
hold, ordinary success and existing empty-target refusal. The two timing controls
use a deliberate 1.3-second loopback response against an admitted eight-second
budget and a later one-second value. The fixture separately drains an old raw
native POST after timeout; it does not count that cleanup as product ownership.
An original and alternate endpoint expose changed resolver environment/CWD through
actual requests and file inventory. Supplied fixture model files are inventory
bytes only; no local model, external provider or model inference is executed.

No runtime or installed claim follows from source-only AST/Ruff/apply checks.
The root-owned opening and closing are recorded below. Source,
provider, helper and patch hashes are bound in the scratch receipt; existing
streaming/cancellation/schema controls remain required regression proof.

The separate streaming provider implementation still has ambient network/stream
mode selection, raw native nonstream/fallback requests, native client construction,
client/iterator cleanup and outer waiter ownership obligations. These remain
explicitly outside this input slice. Its empty-target guard did not establish
nonempty BLOCKED-target refusal. That distinct admission correction and its actual
quarantine/GGUF controls are recorded separately in
`docs/architecture/CONTRACT_DELTA_MODEL_STREAM_ADMISSION_D_2026-09-28.md`.
Durable resolver authority is
`docs/specs/PROVIDER_GOVERNANCE_COMMAND_OWNERSHIP.md`; this scope does not complete D.

## Observed source proof, 2026-09-28

Windows Python 3.11 opening: nine failures and seven passes in 19.16s, with
5,634 unchanged Git-visible inputs. Five input controls expose mutated requests,
API keys, inference/turn deadlines and resolver environment/CWD. Four admission
controls physically show nonempty BLOCKED targets constructing a provider,
posting completion requests and producing successful workload intents. Both turn
phase controls pass on unchanged product. The reports retain each failed case
and actual local HTTP/event/commit readback before assertions.

After the separately reviewed input, admission and turn changes, the combined
Windows Python 3.11 selection passes 364 cases in 221.01s (one upstream warning),
5,638 unchanged inputs. Python 3.12.2 source proof passes 94 cases in 57.89s on
the same 5,638 inputs, including all fourteen workload controls, both turn phase
controls, all 22 tool ownership controls and streaming/provider guards. This is
live local HTTP/file/SQLite and controlled-provider integration proof (primary,
success). Fixture catalog/model bytes do not establish actual model inference.
The Python 3.12 environment name includes installed, but imports are from source;
neither campaign is a fresh installed-artifact acceptance run.

Evidence: `.tmp/goal-20260928-model-turn-opening-v1-*`,
`.tmp/goal-20260928-model-opening-physical-readback.json`,
`.tmp/goal-20260928-model-turn-tool-closing-v1-*`, and
`.tmp/goal-20260928-model-turn-tool-source-py312-v1-*`.
Wider provider/generator/waiter lifetime, canonical quality, installed/Linux and
CAP acceptance remain open. No version bump or whole-lane completion follows.
