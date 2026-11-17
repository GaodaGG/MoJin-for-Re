"""Run the real SDL overlay host against isolated settings; export reviewable UI."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from PIL import Image
from prepare_runtime import prepare

DEV=Path(__file__).resolve().parents[1]
ROOT=DEV.parent
SRC=DEV/'third_party/nakagawa'
prepare()
out=DEV/'tests/settings-ui'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True)
toolroot=DEV/'toolchain/msys64/ucrt64'
env=os.environ.copy()
env.update(PATH=str(toolroot/'bin')+os.pathsep+env['PATH'], SDL_VIDEODRIVER='dummy', SR_REDUCE_MOTION='on')
env['SR_MOJIN_CJK_FONT']=str(DEV/'assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf')
env['SR_MOJIN_TTF_LIBRARY']=str(toolroot/'bin/SDL3_ttf.dll')
inventory=(SRC/'mk/nk_ui.mk').read_text(encoding='utf-8')
sources=[]
for group in ['NK_UI_CORE_SRCS','NK_UI_EDGE_SRCS','NK_UI_OVERLAY_C9C_SRCS','NK_UI_OVERLAY_HOST_SRCS']:
    block=re.search(r'^'+group+r' := (.*?)(?:\n\n)',inventory,re.M|re.S).group(1)
    sources += [SRC/s for s in re.findall(r'src/[\w/]+\.c',block)]
sources += [SRC/'src/ui/backend/nk_ui_sdlr.c',SRC/'src/core/nk_shared_helpers.c',SRC/'src/core/nk_input_profile.c',SRC/'src/core/nk_json.c',SRC/'src/core/nk_platform_win32.c',DEV/'runtime/graphics_settings.c',DEV/'tests/graphics_settings_test.c']
sources=[DEV/'generated/runtime'/p.name if p.name in {'nk_overlay.c','overlay_quick.c','overlay_host.c'} else p for p in sources]
exe=out/'settings-test.exe'
command=[str(toolroot/'bin/gcc.exe'),'-std=c11','-O1','-fno-strict-aliasing','-Wall','-Wextra','-Werror','-DNK_UI_WITH_SDL','-DNK_UI_WITH_SDL3','-DNK_UI_WITH_SDL_TTF']
command += ['-I'+str(p) for p in [SRC/'src/ui',SRC/'src/rt/overlay',SRC/'src/core',SRC/'third_party/clay',DEV/'runtime',toolroot/'include']]
command += [str(p) for p in sources]+['-L'+str(toolroot/'lib'),'-lSDL3','-lole32','-lshell32','-ladvapi32','-luuid','-lm','-o',str(exe)]
result=subprocess.run(command,env=env,cwd=ROOT,capture_output=True)
(out/'compile.log').write_bytes(result.stdout+result.stderr)
if result.returncode:
    print((result.stdout+result.stderr).decode('utf-8',errors='replace')[-6000:]); raise SystemExit(result.returncode)
result=subprocess.run([str(exe),str(out),str(SRC)],env=env,cwd=ROOT,capture_output=True)
(out/'test.log').write_bytes(result.stdout+result.stderr)
for p in out.glob('*.bmp'):
    with Image.open(p) as im: im.save(p.with_suffix('.png'))
record=dict(output=str(out),exit_code=result.returncode,command=command,
    executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    boundaries=['Real overlay host/fonts/input and Windows INI persistence, with synthetic renderer dimensions; no game/GPU verification.'])
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
(DEV/'evidence/graphics-settings-test.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print((result.stdout+result.stderr).decode('utf-8',errors='replace')); print(out)
raise SystemExit(result.returncode)
