"""Native CLI loop with a controlled workload and actual acceptance/publication."""
import sys
from pathlib import Path

import pytest

import orket
import orket.interfaces.cli as cli_module
import orket.organization_loop as loop_module
from orket.cli import main as cli_main
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.integration.test_epic_completion_publication import accept_publication_card


def configure(patch, accept):
    engines, loops, pipelines, results = [], [], [], []
    engine_factory, pipeline_factory = cli_module.OrchestrationEngine, loop_module.ExecutionPipeline
    loop_run = loop_module.OrganizationLoop.run_forever

    def engine(*args, **kwargs):
        owner = engine_factory(*args, **kwargs)
        engines.append(owner)
        return owner

    async def run(self):
        loops.append(self)
        await loop_run(self)

    def pipeline(*args, **kwargs):
        owner = pipeline_factory(*args, **kwargs)
        pipelines.append(owner)
        original_run = owner.run_card

        async def workload(**_kwargs):
            if accept:
                await accept_publication_card(owner, owner.workspace)

        async def observed(*args, **kwargs):
            try:
                result = await original_run(*args, **kwargs)
                results.append({**result.model_dump(mode='json'), 'succeeded': result.succeeded})
                return result
            finally:
                loops[0].running = False

        owner.orchestrator.execute_epic, owner.run_card = workload, observed
        return owner

    patch.setattr(cli_module, 'OrchestrationEngine', engine)
    patch.setattr(loop_module.OrganizationLoop, 'run_forever', run)
    patch.setattr(loop_module, 'ExecutionPipeline', pipeline)
    return engines, loops, pipelines, results


def main():
    root, case = Path(sys.argv[1]), sys.argv[2]
    assert root.is_absolute() and case in {'accepted', 'unfinished'}
    with pytest.MonkeyPatch.context() as patch:
        engines, loops, pipelines, results = configure(patch, case == 'accepted')
        code = cli_main(['runtime', '--loop'])
    write_payload_with_diff_ledger(root / 'cli-observation.json', {
        'path': 'primary', 'proof': 'native canonical CLI, controlled workload, actual card acceptance and SQLite',
        'case': case, 'returncode': code, 'runtime_origin': orket.__file__,
        'engine_closed': [owner._closed for owner in engines], 'pipeline_closed': [owner._closed for owner in pipelines],
        'loops_stopped': [not owner.running for owner in loops],
        'databases': [owner.db_path for owner in pipelines], 'results': results,
    })
    return code


if __name__ == '__main__':
    raise SystemExit(main())
