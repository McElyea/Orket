"""Build the staged canonical candidate and verify the exact publication wheels."""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
import prr_common as p
from prr_candidate import artifacts
from prr_installed import startup


async def sdk_cli(directory,state,python,cell):
    project=p.EXTERNAL/(directory.name+'-'+cell+'-sdk')
    project.mkdir()
    cli=python.parent/'orket.exe'
    result=await p.command(directory,state,[cli,'sdk','--version'],cell+'-sdk-version',project)
    assert result.stdout.decode().strip()=='0.7.2'
    result=await p.command(directory,state,[cli,'sdk','--version','--json'],cell+'-sdk-version-json',project)
    assert json.loads(result.stdout)=={'ok':True,'sdk_version':'0.7.2'}
    for kind in ('default','agent'):
        target=project/kind
        result=await p.command(directory,state,[cli,'ext','init',target,'--kind',kind,'--json'],cell+'-init-'+kind,project)
        assert json.loads(result.stdout)['ok']
        result=await p.command(directory,state,[cli,'ext','validate',target,'--strict','--json'],cell+'-validate-'+kind,project)
        assert json.loads(result.stdout)['ok']


async def main():
    directory,state=p.new_state(sys.argv[1] if len(sys.argv)>1 else 'final-packages')
    result='failure'
    try:
        source=directory/'source'
        source.mkdir()
        state['index_tree']=subprocess.check_output(['git','write-tree'],cwd=p.ROOT,text=True).strip()
        await p.command(directory,state,['git','-c','core.longpaths=true','checkout-index','--all',
            '--prefix='+source.as_posix()+'/'],'snapshot')
        operator=source/p.OPERATOR
        operator.parent.mkdir(parents=True,exist_ok=True)
        operator.write_bytes(subprocess.check_output(['git','show',':'+p.OPERATOR],cwd=p.ROOT))
        state['snapshot']=str(source)
        state['canonical_snapshot_sha256']={path.relative_to(source).as_posix():p.sha(path)
            for path in source.rglob('*') if path.is_file()}
        output=directory/'artifacts'
        for label,root in [('sdk',source/'orket_extension_sdk'),('core',source)]:
            name='orket_extension_sdk' if label=='sdk' else 'orket'
            await p.command(directory,state,[p.UV,'build','--sdist','--python',sys.executable,
                '--no-python-downloads','--out-dir',output,root],label+'-sdist',source)
            await p.command(directory,state,[p.UV,'build','--wheel','--python',sys.executable,
                '--no-python-downloads','--out-dir',output,output/(name+'-0.7.2.tar.gz')],label+'-wheel',source)
        artifacts(directory,state,source)
        for name,row in state['artifacts'].items():
            row['sdist']=str(output/(name+'-0.7.2.tar.gz'))
            row['sdist_sha256']=p.sha(row['sdist'])
        constraints=p.BASE/'candidate-r02/dependency-constraints.txt'
        for cell,base in p.PYTHONS.items():
            env=p.EXTERNAL/(directory.name+'-'+cell)
            await p.command(directory,state,[p.UV,'venv','--no-project','--seed','--no-python-downloads',
                '--python',base,env],cell+'-venv',p.EXTERNAL)
            python=env/'Scripts/python.exe'
            await p.command(directory,state,[python,'-m','pip','install','--constraint',constraints,
                *[row['path'] for row in state['artifacts'].values()]],cell+'-install',p.EXTERNAL)
            await p.command(directory,state,[python,'-m','pip','check'],cell+'-pip-check',p.EXTERNAL)
            for kind,extra in [('journey',[]),('parser',['--parser-proof'])]:
                project=p.EXTERNAL/(directory.name+'-'+cell+'-'+kind)
                project.mkdir()
                shutil.copyfile(source/'server.py',project/'server.py')
                await p.command(directory,state,[python,'-I',p.ROOT/'.tmp/prr_journey.py',project,'0.7.2',*extra],
                    cell+'-'+kind,project,seconds=360)
            for initialized in (False,True):
                await startup(directory,state,python,cell,initialized)
            await sdk_cli(directory,state,python,cell)
            await p.command(directory,state,[python,'-m','pip','freeze'],cell+'-dependencies',p.EXTERNAL)
        env=p.EXTERNAL/'final-sdk-only'
        await p.command(directory,state,[p.UV,'venv','--no-project','--seed','--no-python-downloads',
            '--python',p.PYTHONS['py311'],env],'sdk-only-venv',p.EXTERNAL)
        python=env/'Scripts/python.exe'
        await p.command(directory,state,[python,'-m','pip','install','--constraint',constraints,
            state['artifacts']['orket_extension_sdk']['path']],'sdk-only-install',p.EXTERNAL)
        code='import importlib.util,importlib.metadata,json,sys;import orket_extension_sdk as sdk;from pathlib import Path;assert sdk.__version__==importlib.metadata.version("orket-extension-sdk")=="0.7.2";assert importlib.util.find_spec("orket") is None;assert Path(sdk.__file__).is_relative_to(Path(sys.prefix)/"Lib/site-packages");print(json.dumps({"version":sdk.__version__,"origin":sdk.__file__,"host_namespace_absent":True}))'
        await p.command(directory,state,[python,'-I','-c',code],'sdk-only-import',p.EXTERNAL)
        await p.command(directory,state,[python,'-m','pip','check'],'sdk-only-pip-check',p.EXTERNAL)
        result='success'
    finally:
        p.finish(directory,state,result)


if __name__=='__main__':asyncio.run(main())
