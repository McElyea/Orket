"""Transport projections and continuation gates for application runtime results."""
from orket.core.contracts.runtime_execution_result import RuntimeCollectionResult, RuntimeExecutionResult
from orket.exceptions import ExecutionFailed

RuntimeResult = RuntimeExecutionResult | RuntimeCollectionResult


class RuntimeOutcomeError(ExecutionFailed):
    def __init__(self, result: RuntimeResult):
        self.result = result
        super().__init__(result.reason or f"Runtime {result.session_id} did not establish success")


def runtime_result_exit_code(result: RuntimeResult) -> int:
    if not isinstance(result, (RuntimeExecutionResult, RuntimeCollectionResult)):
        raise TypeError("E_RUNTIME_RESULT_TYPED_OUTCOME_REQUIRED")
    if isinstance(result, RuntimeExecutionResult) and result.observation == "cancelled":
        return 130
    return 0 if result.succeeded else 1


def require_runtime_success(result: RuntimeResult) -> RuntimeResult:
    if runtime_result_exit_code(result) != 0:
        raise RuntimeOutcomeError(result)
    return result


def runtime_result_payload(result: RuntimeResult) -> dict:
    runtime_result_exit_code(result)
    return {**result.model_dump(mode="json"), "succeeded": result.succeeded}


def runtime_result_lines(result: RuntimeResult) -> list[str]:
    code = runtime_result_exit_code(result)
    lines = [f"Runtime {result.session_id}: {'success' if code == 0 else 'not successful'}"]
    if isinstance(result, RuntimeExecutionResult):
        state = result.lifecycle_state.value if result.lifecycle_state else "unobserved"
        lines.append(f"Observation: {result.observation}; lifecycle: {state}; result: {result.result_class.value}")
        lines.extend(f"Evidence: {reference}" for reference in result.evidence_refs)
    else:
        lines.append(f"Collection members observed: {len(result.members)}/{len(result.expected_members)}")
        for member in result.members:
            lines.extend([f"Member: {member.target}", *runtime_result_lines(member.result)])
    if result.reason:
        lines.append(f"Reason: {result.reason}")
    return lines
