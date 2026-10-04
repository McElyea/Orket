import asyncio
import shutil
import sys
import prr_common as p
from prr_installed import startup


async def main():
    directory,state=p.new_state(sys.argv[1])
    result='failure'
    failures=[]
    try:
        for cell in p.PYTHONS:
            python=p.EXTERNAL / ('installed-r03-'+cell) / 'Scripts/python.exe'
            project=p.EXTERNAL / (directory.name+'-'+cell+'-parser')
            project.mkdir()
            shutil.copyfile(p.BASE/'candidate-r02/source/server.py',project/'server.py')
            try:
                await p.command(directory,state,[python,'-I',p.ROOT/'.tmp/prr_journey.py',project,'0.7.2',
                    '--parser-proof'],cell+'-parser',project,seconds=360)
            except AssertionError as error:
                failures.append(dict(cell=cell,error=str(error)))
            await startup(directory,state,python,cell,True)
        state['failures']=failures
        assert not failures,failures
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
