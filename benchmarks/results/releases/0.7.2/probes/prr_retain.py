"""Preserve PRR captures byte-for-byte and project bounded release observations."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile
import prr_common as p

OUT=p.ROOT/'benchmarks/results/releases/0.7.2'
BATCHES=['baseline','baseline-upgrade','parser-prefixed','parser-repaired','candidate-r01',
    'websocket-prefixed','websocket-repaired','candidate-r02','installed-r03',
    'live-remainder-r04','live-remainder-r05','live-remainder-r06','live-remainder-r07','verification',
    'verification-corrected','final-packages','final-packages-r02','documented-probe',
    'environment-refresh','profiled-refresh-r02']


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    assert p.sha(source)==p.sha(target)


def retain_batch(name):
    directory=p.BASE/name
    state=json.loads((directory/'state.json').read_text(encoding='utf-8'))
    assert state['status']=='finished' and state['source_inputs_unchanged']
    target=OUT/'batches'/name
    target.mkdir(parents=True,exist_ok=True)
    raw=(directory/'state.json').read_bytes()
    (target/'state.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress((target/'state.json.gz').read_bytes())==raw
    for row in state['commands']:
        assert row['status']=='finished' and row['lifetime']['cleanup_confirmed'] and row['lifetime']['capture_complete']
        for stream in ('stdout','stderr'):
            source=Path(row[stream]['path'])
            assert p.sha(source)==row[stream]['sha256']
            copy(source,target/source.name)
    for source in directory.glob('*.xml'):
        copy(source,target/source.name)
    return dict(observed_result=state['observed_result'],raw_receipt_sha256=p.sha(directory/'state.json'),
        source_inputs_unchanged=True,command_count=len(state['commands']),all_native_cleanup_confirmed=True,
        receipt=(target/'state.json.gz').relative_to(p.ROOT).as_posix())


def retain_project(project):
    target=OUT/'projects'/project.name
    retained=[]
    for name in ('journey.json','turn-live.json','workspace/grounded.txt'):
        if (project/name).is_file():
            copy(project/name,target/name)
            retained.append(name)
    for relative in ('workspace/interactions','workspace/observability','observability','model'):
        directory=project/relative
        if directory.is_dir():
            for source in sorted(directory.rglob('*')):
                if source.is_file() and source.suffix in ('.json','.jsonl'):
                    rel=source.relative_to(project)
                    copy(source,target/rel)
                    retained.append(rel.as_posix())
    return dict(original_project=str(project),retained_files=retained)


def package_audit():
    artifact_root=p.BASE/'final-packages-r02/artifacts'
    entries=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=p.ROOT).split(b'\0')
    index={row.split(b'\t',1)[1].decode():row.split(b'\t',1)[0].split()[1].decode() for row in entries if row}
    checked=[]
    for archive in sorted(artifact_root.glob('*.tar.gz')):
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if not member.isfile():continue
                relative='/'.join(member.name.split('/')[1:])
                source=p.ROOT/relative if archive.name.startswith('orket-') else p.ROOT/'orket_extension_sdk'/relative
                if source.is_file() and '.egg-info/' not in relative:
                    data=tar.extractfile(member).read()
                    name=source.relative_to(p.ROOT).as_posix()
                    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                    assert blob==index[name],(archive.name,relative)
                    checked.append(dict(artifact=archive.name,source=name,sha256=hashlib.sha256(data).hexdigest(),git_blob=blob))
    normalized={}
    for namespace in ('orket','orket_extension_sdk'):
        name=namespace+'-0.7.2-py3-none-any.whl'
        def members(batch):
            with zipfile.ZipFile(p.BASE/batch/'artifacts'/name) as archive:
                return {item:archive.read(item) for item in archive.namelist()
                    if item.startswith(namespace+'/') and not item.endswith('/')}
        old,new=members('candidate-r02'),members('final-packages-r02')
        assert old.keys()==new.keys()
        changed=[name for name in old if old[name]!=new[name]]
        assert all(old[name].replace(b'\r\n',b'\n')==new[name] for name in changed)
        normalized[namespace]=changed
    p.write(OUT/'packaged-source.json',dict(observed_result='success',exact_source_members=checked,
        canonical_newline_only_changes_from_candidate_r02=normalized))
    artifacts=[source for source in sorted(artifact_root.iterdir()) if source.suffix=='.whl' or source.name.endswith('.tar.gz')]
    constraints=OUT/'dependency-constraints-0.7.2.txt'
    copy(p.BASE/'candidate-r02/dependency-constraints.txt',constraints)
    sums=''.join(p.sha(source)+'  '+source.name+'\n' for source in artifacts+[constraints])
    (OUT/'SHA256SUMS.txt').write_text(sums,encoding='utf-8',newline='\n')
    for source in artifacts:
        target=p.ROOT/'dist'/source.name
        assert not target.exists() or p.sha(target)==p.sha(source)
        copy(source,target)
    copy(constraints,p.ROOT/'dist'/constraints.name)
    copy(OUT/'SHA256SUMS.txt',p.ROOT/'dist/SHA256SUMS-0.7.2.txt')
    return len(checked)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records={name:retain_batch(name) for name in BATCHES}
    assert records['verification-corrected']['observed_result']==records['live-remainder-r07']['observed_result']=='success'
    assert records['final-packages-r02']['observed_result']=='success'
    projects={}
    for project in sorted(p.EXTERNAL.iterdir()):
        if project.is_dir() and (any((project/name).is_file() for name in ('journey.json','turn-live.json'))
                                or project.name.endswith(('-initialized','-missing-board'))):
            projects[project.name]=retain_project(project)
    for name in ('prr_common.py','prr_journey.py','prr_installed.py','prr_turn_live.py','prr_live_remainder.py',
                 'prr_candidate.py','prr_verify.py','prr_corrected.py','prr_final.py','prr_retain.py','prr_docs_probe.py',
                 'prr_environment_refresh.py','prr_profiled_refresh.py'):
        copy(p.ROOT/'.tmp'/name,OUT/'probes'/name)
    suite=ET.parse(p.BASE/'verification/py311-controls.xml').getroot()[0]
    additional=ET.parse(p.BASE/'verification/py312-controls.xml').getroot()[0]
    for item in (suite,additional):
        assert all(int(item.attrib[key])==0 for key in ('errors','failures','skipped'))
    count=package_audit()
    p.write(OUT/'verification.json',dict(schema='orket.release.0.7.2.verification.v1',version='0.7.2',
        proof_mode='live_and_structural_separately_identified',observed_path='primary',observed_result='success',
        batches=records,projects=projects,source_controls=suite.attrib,additional_installed_controls=additional.attrib,
        packaged_source_members=count,
        evidence_semantics='Raw native logs, XML, project reports and compressed local receipts retain exact bytes. Embedded original absolute paths identify the originating environment; project copies preserve relative structure.',
        probe_semantics='Probe sources are the final working local harnesses; earlier failures/logs retain their actual assertions. They are release evidence, not new canonical product entrypoints.',
        limits=['Initial direct profiled flow refused the embedded template. Independent server replacement aligned the template; bounded actual TurnExecutor/file-write/grounding flows then passed on both versions, without bypass. No general card-workflow claim.',
            'Missing CLI board is intentionally degraded; initialized startup passes.',
            'No fresh full coverage, hosted CI, Linux/Mac, Docker, remote Gitea or remote inference termination proof.',
            'Durable commits bind lifecycle intents, not generated transcripts; captured event bytes are separate.',
            'One extra streaming probe failed closed with provider_error; subsequent bounded live parser probes pass; no arbitrary reliability guarantee.']))
    print(json.dumps(dict(source_controls=suite.attrib,additional_installed_controls=additional.attrib,
        packaged_source_members=count,files=len([x for x in OUT.rglob('*') if x.is_file()]))))


if __name__=='__main__':main()
