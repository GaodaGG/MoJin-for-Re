"""Verify a completed game-integrated Esc capture; never claim full-game acceptance."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('run',type=Path)
args=parser.parse_args()
run=args.run.resolve()
if not run.is_relative_to(ROOT/'development/tests/runs'):
    parser.error('Use a private game probe')
record=json.loads((run/'run.json').read_text(encoding='utf-8'))
assert record['exit_code']==0 and not record['timed_out']
mode=record['environment'].get('SR_MOJIN_SETTINGS_PROBE')
assert mode in ('1','save')
log=(run/'stderr.log').read_text(encoding='utf-8',errors='replace')
assert 'received=down key=27 repeat=0 claim=0 text=0' in log
assert 'SR_PAUSE: entered source=user' in log
assert 'SR_PAUSE: resumed' in log
assert 'Guest requested exit (sceKernelExitGame())' in log
assert 'interp_entries=0 entries_dispatch_miss=0' in log
m=re.search(r'MOJIN_SETTINGS_CAPTURE saved=1 scene=(\d+)x(\d+) composition=(\d+)x(\d+) output=(\d+)x(\d+) ssaa=(\d+)',log)
assert m,'No actual in-game settings capture'
sw,sh,cw,ch,ow,oh,aa=map(int,m.groups())
assert (sw,sh)==(cw*aa,ch*aa)
capture=run/'settings.bmp'
with Image.open(capture) as im:
    assert im.size==(ow,oh)
    im.save(run/'settings.png')
result=dict(run=str(run),executable_sha256=record['executable_sha256'],
    image_sha256=record['image_sha256'],exit_code=record['exit_code'],
    elapsed_seconds=record['elapsed_seconds'],
    actual_scene=[sw,sh],actual_composition=[cw,ch],actual_output=[ow,oh],active_ssaa=aa,
    capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
    boundaries=['Own-process SDL Esc through normal input path, pause, actual GPU dimensions, normal quit.',
                'Not desktop input, not battle/save-progress acceptance, not high-FPS or physical 4K validation.',
                'Layout still requires visual inspection of the actual game capture.'])
if mode=='save':
    def settings(path):
        raw=path.read_bytes()
        parser=configparser.ConfigParser()
        parser.read_string(raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'))
        return {key:parser.getint('Graphics',key) for key in ['RenderScale','SSAA','WindowWidth','WindowHeight','Fullscreen']}
    expected=dict(RenderScale=3,SSAA=1,WindowWidth=1280,WindowHeight=720,Fullscreen=0)
    original=dict(RenderScale=4,SSAA=2,WindowWidth=960,WindowHeight=544,Fullscreen=0)
    assert settings(run/'settings.ini')==expected
    assert settings(run/'settings.ini.previous')==original
    assert 'MOJIN_SETTINGS saved scale=3 ssaa=1 window=1280x720 fullscreen=0' in log
    assert log.index('SR_PAUSE: resumed')<log.index('MOJIN_SETTINGS_PROBE sent=quit')
    assert (sw,sh,cw,ch,ow,oh,aa)==(3840,2176,1920,1088,960,544,2)
    result['saved_options']=expected
    result['settings_sha256']=hashlib.sha256((run/'settings.ini').read_bytes()).hexdigest()
    result['backup_matches_original']=True
    result['resumed_before_quit']=True
(run/'settings-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(ROOT/'development/evidence/settings-game-test.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
