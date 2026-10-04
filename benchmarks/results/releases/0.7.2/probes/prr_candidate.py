"""Build canonical frozen PRR wheels and exercise installed native Windows paths."""
import asyncio
from email.parser import Parser
import shutil
import subprocess
import sys
import zipfile
import prr_common as p


def snapshot(directory, state):
    source = directory / 'source'
    source.mkdir()
    for name, digest in state['source_sha256'].items():
        target = source / name
        assert target.resolve().is_relative_to(source.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == p.OPERATOR:
            target.write_bytes(subprocess.check_output(['git','show','HEAD:'+name], cwd=p.ROOT))
        else:
            shutil.copyfile(p.ROOT / name, target)
        assert p.sha(target) == digest, name
    state['snapshot'] = str(source)
    return source


def artifacts(directory, state, source):
    rows = {}
    for namespace in ('orket', 'orket_extension_sdk'):
        wheel = directory / 'artifacts' / (namespace + '-0.7.2-py3-none-any.whl')
        with zipfile.ZipFile(wheel) as archive:
            metadata = Parser().parsestr(archive.read(next(name for name in archive.namelist()
                                                          if name.endswith('.dist-info/METADATA'))).decode())
            members = {name:archive.read(name) for name in archive.namelist()
                       if name.startswith(namespace + '/') and not name.endswith('/')}
        assert metadata['Version'] == '0.7.2'
        if namespace == 'orket':
            assert 'orket-extension-sdk==0.7.2' in metadata.get_all('Requires-Dist')
            assert any(value.startswith('websockets') for value in metadata.get_all('Requires-Dist'))
        for name, data in members.items():
            assert data == (source / name).read_bytes(), name
        rows[namespace] = dict(path=str(wheel), sha256=p.sha(wheel), namespace_members=len(members),
                               source_bytes_match=True)
    state['artifacts'] = rows
    p.write(directory / 'state.json', state)


async def main():
    batch = sys.argv[1] if len(sys.argv) > 1 else 'candidate-r01'
    directory, state = p.new_state(batch)
    result = 'failure'
    try:
        source = snapshot(directory, state)
        output = directory / 'artifacts'
        constraints = directory / 'dependency-constraints.txt'
        shutil.copyfile(p.BASE / 'baseline/dependency-constraints.txt', constraints)
        for label, root in [('sdk', source / 'orket_extension_sdk'), ('core', source)]:
            name = 'orket_extension_sdk' if label == 'sdk' else 'orket'
            await p.command(directory, state, [p.UV,'build','--sdist','--python',sys.executable,
                '--no-python-downloads','--out-dir',output,root], label + '-sdist', source)
            await p.command(directory, state, [p.UV,'build','--wheel','--python',sys.executable,
                '--no-python-downloads','--out-dir',output,output / (name + '-0.7.2.tar.gz')], label + '-wheel', source)
        artifacts(directory, state, source)
        for cell, base in p.PYTHONS.items():
            env_dir = p.EXTERNAL / (batch + '-' + cell)
            await p.command(directory, state, [p.UV,'venv','--no-project','--seed','--no-python-downloads',
                '--python',base,env_dir], cell + '-venv', p.EXTERNAL)
            python = env_dir / 'Scripts/python.exe'
            await p.command(directory, state, [p.UV,'pip','install','--python',python,'--constraint',constraints,
                *[item['path'] for item in state['artifacts'].values()]], cell + '-install', p.EXTERNAL)
            await p.command(directory, state, [python,'-m','pip','check'], cell + '-pip-check', p.EXTERNAL)
            project = p.EXTERNAL / (batch + '-' + cell + '-project')
            project.mkdir()
            shutil.copyfile(source / 'server.py', project / 'server.py')
            await p.command(directory, state, [python,'-I',p.ROOT / '.tmp/prr_journey.py',project,'0.7.2'],
                            cell + '-journey', project, seconds=360)
        result = 'success'
    finally:
        p.finish(directory, state, result)


if __name__ == '__main__':
    asyncio.run(main())
