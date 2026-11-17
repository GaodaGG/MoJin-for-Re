"""Verify no-argument startup consumed the UI-saved settings and created that renderer."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(); parser.add_argument('stage',type=Path); args=parser.parse_args()
stage=args.stage.resolve()
if not stage.is_relative_to(ROOT/'development/tests/standalone'):
    parser.error('Use a private restart stage')
manifest=json.loads((stage/'stage-manifest.json').read_text(encoding='utf-8'))
test=json.loads((stage/'standalone-test.json').read_text(encoding='utf-8'))
assert test['exit_code']==0 and test['close_requested'] and not test.get('timed_out_after_close')
assert test['argc']==1 and not test['path_has_toolchain']
assert manifest['executable_sha256']==test['executable_sha256']
assert hashlib.sha256((stage/'settings.ini').read_bytes()).hexdigest()==manifest['settings_sha256']
assert len(test['logs'])==1
log=(ROOT/test['logs'][0]).read_text(encoding='utf-8',errors='replace')
o=manifest['expected_options']; scale=o['RenderScale']; aa=o['SSAA']
assert f"render={scale} ssaa={aa} output_request={o['WindowWidth']}x{o['WindowHeight']}" in log
if 'FPS' in o:
    assert f"fps={o['FPS']}" in log
    assert 'MOJIN_FRAME_CLOCK target=120' in log
assert f'MOJIN_RENDER composition={480*scale}x{272*scale}' in log
assert 'BOOT_EVENT phase=first_frame source=gpu presented=1' in log
assert 'Guest requested exit (sceKernelExitGame())' in log
assert 'interp_entries=0 entries_dispatch_miss=0' in log
assert aa==1 and 'ACE_MODE: on' not in log # This check intentionally targets the 4/2 -> 3/1 scenario.
swap=re.search(r'sdl3vk: init ok \((\d+)x(\d+) swapchain',log)
assert swap and tuple(map(int,swap.groups()))==(o['WindowWidth'],o['WindowHeight'])
result=dict(stage=str(stage),source_run=manifest['source_run'],executable_sha256=test['executable_sha256'],
    requested=o,actual_scene=[480*scale,272*scale],actual_composition=[480*scale,272*scale],
    actual_swapchain=list(map(int,swap.groups())),normal_exit=True,
    boundary='UI save and no-argument renderer restart verified for scale3/SSAA1/1280x720; not game progress or all graphics settings.',
    log=test['logs'][0],log_sha256=hashlib.sha256((ROOT/test['logs'][0]).read_bytes()).hexdigest())
(stage/'settings-restart-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(ROOT/'development/evidence/settings-restart-test.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
