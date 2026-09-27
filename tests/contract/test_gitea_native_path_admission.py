"""Layer: contract. Supplied native-name outcomes cannot select another repository."""
import asyncio
from pathlib import Path

import pytest

import orket.adapters.vcs.gitea_git_paths as paths

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['unshortened', 'relative', 'missing', 'wrong-directory', 'file', 'native-error'])
async def test_native_repository_spelling_refuses_unusable_observations(tmp_path, monkeypatch, kind):
    repo, other = tmp_path / 'repo', tmp_path / 'other'
    await asyncio.to_thread((repo / '.git').mkdir, parents=True)
    await asyncio.to_thread(other.mkdir)
    file = tmp_path / 'file'
    await asyncio.to_thread(file.write_bytes, b'ordinary file')

    def supplied(path):
        if kind == 'native-error':
            raise OSError('controlled native lookup failure')
        if path == repo:
            return repo
        return {'unshortened': tmp_path / ('p' * 230), 'relative': Path('.git'),
                'missing': tmp_path / 'missing', 'wrong-directory': other, 'file': file}[kind]

    monkeypatch.setattr(paths, '_short_path', supplied)
    with pytest.raises(RuntimeError, match='^E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE$'):
        await asyncio.to_thread(paths.native_repository_arguments, repo, initialize=False)


async def test_native_repository_spelling_refuses_event_loop_before_lookup(tmp_path, monkeypatch):
    def forbidden(path):
        pytest.fail('native lookup ran on event loop')

    monkeypatch.setattr(paths, '_short_path', forbidden)
    with pytest.raises(RuntimeError, match='^E_GITEA_GIT_PATH_REQUIRES_ASYNC_OWNER$'):
        paths.native_repository_arguments(tmp_path, initialize=True)
    assert not await asyncio.to_thread((tmp_path / '.git').exists)
