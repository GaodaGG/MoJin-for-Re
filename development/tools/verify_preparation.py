"""Check real startup/preparation traces, not inferred success from a build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('run',type=Path)
args = parser.parse_args()
run=args.run.resolve()
assert run.is_relative_to(ROOT/'development/tests/runs')
meta=json.loads((run/'run.json').read_text(encoding='utf-8'))
assert meta['exit_code']==0 and not meta['timed_out']
exe=Path(meta['command'][0])
assert hashlib.sha256(exe.read_bytes()).hexdigest()==meta['executable_sha256']
log=(run/'stderr.log').read_text(encoding='utf-8',errors='replace')
env=meta['environment']
trace=run/'pipelines.jsonl'
rows=[json.loads(x) for x in trace.read_text().splitlines()] if trace.exists() else []
assert all(x['result']==0 for x in rows)
phases={name:[x for x in rows if x['phase']==name] for name in ('preparation','draw')}
end=re.search(r'MOJIN_PREPARATION end completed=(\d+) total=(\d+) failures=(\d+) stop=(\d+) elapsed_ms=([\d.]+)',log)
if env['SR_MOJIN_PREPARE']=='0':
    assert 'MOJIN_PREPARATION skipped=disabled' in log and not phases['preparation']
elif 'SR_MOJIN_PREP_CANCEL_AT' in env:
    assert end and end[4]=='1' and 'stopped_before_guest reason=1' in log
    assert 'phase=guest_start' not in log and 'Guest requested exit' not in log
    assert not list((run/'memstick').rglob('SAVE'))
else:
    assert end and end[1]==end[2] and end[3]==end[4]=='0'
    assert log.index('MOJIN_PREPARATION end')<log.index('phase=guest_start')
    assert 'interp_entries=0 entries_dispatch_miss=0' in log
    assert 'Guest requested exit (sceKernelExitGame())' in log
    assert 'started empty, saved' in log, 'Must use a fresh application-private pipeline cache'
    if env.get('SR_MOJIN_PREP_LIMIT')=='1':
        assert len(phases['preparation'])==1 and phases['draw'], 'Partial catalog must retain normal missing pipelines'
images=[]
for path in sorted(run.glob('preparation-*.bmp')):
    with Image.open(path) as im:
        im.save(path.with_suffix('.png'))
        images.append(dict(path=path.name,size=list(im.size),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
result=dict(run=str(run.relative_to(ROOT)),executable_sha256=meta['executable_sha256'],
    normal_exit=True,elapsed_seconds=meta['elapsed_seconds'],
    phases={name:dict(creations=len(items),creation_ms=sum(x['elapsed_ns'] for x in items)/1e6) for name,items in phases.items()},
    progress=end.groups() if end else None,images=images,
    boundaries=['Application-private cache starts empty; driver-wide cache not cleared.',
                'Progress appearance still needs visual inspection; elapsed time is not a full-game stutter guarantee.'])
(run/'preparation-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
