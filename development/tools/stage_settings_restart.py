"""Stage an isolated no-argument restart from settings saved through the actual UI.

Hard-link immutable dependencies from an intact candidate; copy the executable
and settings, and keep saves, logs and caches private. No ISO duplication.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser()
parser.add_argument('run',type=Path)
parser.add_argument('template',type=Path)
args=parser.parse_args()
run=args.run.resolve(); template=args.template.resolve()
if not run.is_relative_to(ROOT/'development/tests/runs') or not template.is_relative_to(ROOT/'development/releases'):
    parser.error('Use project-private probe and candidate template directories')
verified=json.loads((run/'settings-verification.json').read_text(encoding='utf-8'))
assert verified['resumed_before_quit'] and verified['backup_matches_original']
assert sha(run/'settings.ini')==verified['settings_sha256']
probe=json.loads((run/'run.json').read_text(encoding='utf-8'))
exe=Path(probe['command'][0]).resolve()
assert exe.is_relative_to(ROOT/'development/generated')
assert sha(exe)==verified['executable_sha256']
release=json.loads((template/'release-manifest.json').read_text(encoding='utf-8'))
assert release['build']['image_sha256']==verified['image_sha256']
for name,row in release['files'].items():
    source=(template/name).resolve()
    assert source.is_relative_to(template) and not source.is_symlink() and sha(source)==row['sha256'],name
out=ROOT/'development/tests/standalone'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True)
links={}
for name,row in release['files'].items():
    if name in ('MoJin.exe','settings.ini'):
        continue
    source=template/name; target=out/name
    target.parent.mkdir(parents=True,exist_ok=True)
    os.link(source,target)
    links[name]=dict(source=str(source.relative_to(ROOT)),sha256=row['sha256'])
shutil.copy2(exe,out/'MoJin.exe')
shutil.copy2(run/'settings.ini',out/'settings.ini')
for name in ('saves','userdata','logs'): (out/name).mkdir(exist_ok=True)
stage=dict(source_run=str(run.relative_to(ROOT)),template=str(template.relative_to(ROOT)),
    executable_sha256=sha(out/'MoJin.exe'),settings_sha256=sha(out/'settings.ini'),
    expected_options=verified['saved_options'],shared_immutable_files=links,
    preservation='Own copies of EXE/settings; private saves/cache/logs; hard links only for static runtime dependencies.')
(out/'stage-manifest.json').write_text(json.dumps(stage,indent=2)+'\n',encoding='utf-8')
print(out)
