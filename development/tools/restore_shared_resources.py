"""Restore missing runtime resource links after a verified preview ZIP restore.

Run disc_data.py extract first if the shared resource tree is absent. Existing
resource bytes are checked, never overwritten; settings/saves are untouched.
"""
import argparse
import json
import os
from pathlib import Path
from disc_data import ROOT, DATA, verify, sha

p=argparse.ArgumentParser(description=__doc__); p.add_argument('runtime',type=Path)
args=p.parse_args(); target=args.runtime.resolve()
assert target.is_relative_to(ROOT) and target!=ROOT
release=json.loads((target/'release-manifest.json').read_text(encoding='utf-8'))
assert release['iso_external'] is False
verify(); checked=[]
for name,row in release['files'].items():
    if not name.startswith('data/game/'): continue
    relative=Path(name.removeprefix('data/game/'))
    source=(DATA/relative).resolve(); out=(target/name).resolve()
    assert source.is_relative_to(DATA) and out.is_relative_to(target)
    assert sha(source)==row['sha256']
    if out.exists():
        assert out.is_file() and sha(out)==row['sha256'], f'Preserve changed file: {out}'
    else:
        out.parent.mkdir(parents=True,exist_ok=True); os.link(source,out)
    assert sha(out)==row['sha256']
    checked.append(name)
print(json.dumps(dict(runtime=str(target),resources_verified=len(checked),existing_files_never_overwritten=True),indent=2))
