import asyncio
import prr_common as p


async def main():
    directory,state=p.new_state('verification-corrected')
    result='failure'
    python=p.EXTERNAL/'verification-py311/Scripts/python.exe'
    try:
        await p.command(directory,state,[python,'-m','ruff','check','orket','tests','orket_extension_sdk'],'ruff')
        await p.command(directory,state,[python,'-m','pytest','-q',
            'tests/integration/test_api_websocket_disconnect.py','tests/integration/test_turn_response_parser_admission.py',
            '--tb=short','--junitxml='+str(directory/'corrected.xml'),
            '--basetemp='+str(directory/'pytest-temp')],'corrected-controls')
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
