import asyncio
import prr_common as p


async def main():
    directory,state=p.new_state('profiled-refresh-r02')
    result='failure'
    try:
        for cell in p.PYTHONS:
            project=p.EXTERNAL/(directory.name+'-'+cell+'-turn-live')
            project.mkdir()
            await p.command(directory,state,[p.EXTERNAL/('final-packages-r02-'+cell)/'Scripts/python.exe','-I',
                p.ROOT/'.tmp/prr_turn_live.py',project],cell+'-profiled-turn',project,seconds=360)
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
