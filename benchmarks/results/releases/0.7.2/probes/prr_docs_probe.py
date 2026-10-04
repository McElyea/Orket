import asyncio
import shutil
import prr_common as p


async def main():
    directory,state=p.new_state('documented-probe')
    result='failure'
    try:
        project=p.EXTERNAL/'documented-probe'
        project.mkdir()
        shutil.copyfile(p.BASE/'final-packages-r02/source/server.py',project/'server.py')
        await p.command(directory,state,[p.EXTERNAL/'final-packages-r02-py311/Scripts/python.exe','-I',
            p.ROOT/'benchmarks/results/releases/0.7.2/probes/prr_journey.py',project,'0.7.2'],
            'documented-journey',project,seconds=360)
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
