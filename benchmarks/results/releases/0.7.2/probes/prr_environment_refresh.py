"""Observe an independently replaced operator process without acquiring ownership."""
import asyncio
import hashlib
import json
import shutil
import httpx
import prr_common as p


async def main():
    directory,state=p.new_state('environment-refresh')
    result='failure'
    try:
        row=await p.command(directory,state,['powershell','-NoProfile','-Command',
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'llama-server.exe' } | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | ConvertTo-Json -Depth 3"],
            'operator-process')
        state['operator_process']=json.loads(row.stdout)
        async with httpx.AsyncClient(trust_env=False,timeout=10) as client:
            props=(await client.get('http://127.0.0.1:8080/props')).json()
            state['model_catalog']=(await client.get('http://127.0.0.1:8080/v1/models')).json()
        expected=(p.BASE/'final-packages-r02/source/orket/runtime/config/qwen38_text_chatml.jinja').read_bytes()
        actual=str(props.get('chat_template') or '').encode()
        state['template_observation']=dict(model_alias=props.get('model_alias'),sha256=hashlib.sha256(actual).hexdigest(),
            matches_candidate=actual==expected,previous_pid=33276,current_pid=state['operator_process']['ProcessId'],
            posture='No task command restarted or stopped either operator process; cause of replacement not asserted.')
        assert props.get('model_alias')==p.MODEL and actual==expected
        p.write(directory/'state.json',state)
        for cell in p.PYTHONS:
            python=p.EXTERNAL/('final-packages-r02-'+cell)/'Scripts/python.exe'
            project=p.EXTERNAL/(directory.name+'-'+cell+'-journey')
            project.mkdir()
            shutil.copyfile(p.BASE/'final-packages-r02/source/server.py',project/'server.py')
            await p.command(directory,state,[python,'-I',p.ROOT/'.tmp/prr_journey.py',project,'0.7.2'],
                cell+'-journey',project,seconds=360)
        project=p.EXTERNAL/(directory.name+'-py311-turn-live')
        project.mkdir()
        await p.command(directory,state,[p.EXTERNAL/'final-packages-r02-py311/Scripts/python.exe','-I',
            p.ROOT/'.tmp/prr_turn_live.py',project], 'profiled-turn',project,seconds=360)
        result='success'
    finally:
        p.finish(directory,state,result)


asyncio.run(main())
