"""Layer: contract. Supplied-port uncertainty, privacy and unchanged command bounds."""
from dataclasses import replace

import pytest

from orket.adapters.vcs.gitea_export_git import GiteaExportGit
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['success', 'uncertain', 'timeout', 'incomplete', 'refused', 'exit'])
async def test_export_command_requires_confirmed_outcome(tmp_path, kind):
    result = OwnedCommandResult(0, b'captured\n', b'private-diagnostic', 'completed', True, True,
                                'fixture-port', 1, 2, 3, ())
    changes = {'success': {}, 'uncertain': {'cleanup_confirmed': False}, 'timeout': {'reason': 'timeout'},
               'incomplete': {'capture_complete': False}, 'refused': {'reason': 'refused'}, 'exit': {'returncode': 7}}
    result = replace(result, **changes[kind])
    calls = []

    class Port:
        async def run(self, argv, **options):
            calls.append((argv, options))
            return result

    git = GiteaExportGit(tmp_path, 'https://fixture.invalid/repo', {'PRIVATE': 'private-input'}, command_runner=Port())
    if kind == 'success':
        assert await git.command('status') == (0, 'captured')
    else:
        expected = CommandExecutionUncertain if kind == 'uncertain' else TimeoutError if kind == 'timeout' else RuntimeError
        with pytest.raises(expected) as outcome:
            await git.command('status')
        assert 'private-' not in str(outcome.value)
        if kind == 'uncertain':
            assert outcome.value.lifetime is result
    assert len(calls) == 1
    assert calls[0][0] == ('git', '-c', 'core.hooksPath=', '-c', 'init.templateDir=', '-c', 'credential.helper=', 'status')
    assert calls[0][1] == dict(cwd=tmp_path, environment={'PRIVATE': 'private-input'},
                              timeout_seconds=60, output_limit_bytes=262144)
