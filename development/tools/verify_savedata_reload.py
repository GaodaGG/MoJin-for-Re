"""Check genuine game-created savedata loaded by a different native process.

This verifies transport and the observed game route, not story progress or all
save slots. Source and destination are private probe directories.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(); parser.add_argument('source',type=Path); parser.add_argument('reload',type=Path)
args=parser.parse_args(); source=args.source.resolve(); reload=args.reload.resolve()
for p in (source,reload):
    if not p.is_relative_to(ROOT/'development/tests/runs'): parser.error('Use private probe runs')
s=json.loads((source/'run.json').read_text(encoding='utf-8'))
r=json.loads((reload/'run.json').read_text(encoding='utf-8'))
assert s['exit_code']==r['exit_code']==0 and not s['timed_out'] and not r['timed_out']
assert s['pid']!=r['pid'] and s['image_sha256']==r['image_sha256']
fixture=r['savedata_restored']; assert fixture['source_run']==source.relative_to(ROOT).as_posix()
assert fixture['source_run_sha256']==hashlib.sha256((source/'run.json').read_bytes()).hexdigest()
assert fixture['files']==s['savedata_after']
for name,row in fixture['files'].items():
    p=source/'memstick/PSP/SAVEDATA'/name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],name
sl=(source/'stderr.log').read_text(encoding='utf-8',errors='replace')
rl=(reload/'stderr.log').read_text(encoding='utf-8',errors='replace')
assert re.search(r'savedata: SAVE .*ULJS00329DATA00[/\\]SAVE \(3744 bytes\)',sl)
loaded=re.search(r'savedata: LOAD .*ULJS00329DATA00 \(3744 bytes\) -> buf=0x[0-9a-f]+ cap=3744 first=48444954',rl)
assert loaded,'No actual game savedata LOAD'
assert 'savedata: SAVE ' not in rl[:loaded.end()],'The game replaced the fixture before loading it'
assert 'result=0x00000000' in rl[loaded.end():loaded.end()+180]
for log in (sl,rl):
    assert 'Guest requested exit (sceKernelExitGame())' in log
    assert 'interp_entries=0 entries_dispatch_miss=0' in log
result=dict(source_run=str(source),reload_run=str(reload),source_exe=s['executable_sha256'],reload_exe=r['executable_sha256'],
    image_sha256=r['image_sha256'],source_pid=s['pid'],reload_pid=r['pid'],
    copied_files=fixture['files'],source_unchanged=True,loaded_bytes=3744,load_result=0,
    reload_render_scale=r['environment'].get('SR_RESOLUTION_SCALE'),
    boundaries=['Game-created initial savedata was copied intact to a new process and loaded successfully before any replacement SAVE.',
                'Does not establish story/character progress, all slots, or full-game save correctness. Inspect the matching scene captures.'])
(reload/'savedata-reload-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(ROOT/'development/evidence/savedata-reload-test.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
