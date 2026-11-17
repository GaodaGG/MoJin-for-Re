"""Relocate all immutable runtime files with regular hardlinks; fresh private data."""
import argparse
import json
import os
from pathlib import Path
import shutil
from disc_data import ROOT, DEV, sha

p=argparse.ArgumentParser(); p.add_argument('package',type=Path); p.add_argument('destination',type=Path)
args=p.parse_args(); source=args.package.resolve(); target=args.destination.resolve()
assert source.is_relative_to(DEV/'releases') and target.is_relative_to(DEV/'tests/standalone')
assert not target.exists() or not any(target.iterdir())
manifest=json.loads((source/'release-manifest.json').read_text(encoding='utf-8'))
assert manifest['iso_external'] is False
for name,row in manifest['files'].items():
    src=(source/name).resolve(); dst=(target/name).resolve()
    assert src.is_relative_to(source) and dst.is_relative_to(target) and sha(src)==row['sha256']
    dst.parent.mkdir(parents=True,exist_ok=True)
    if name=='settings.ini': shutil.copy2(src,dst)
    else: os.link(src,dst)
    assert sha(dst)==row['sha256'] and not dst.is_symlink()
shutil.copy2(source/'release-manifest.json',target/'release-manifest.json')
result=dict(source=str(source),destination=str(target),files_verified=len(manifest['files']),
            regular_files=True,private_settings=True,private_saves=True,iso_in_package=False)
(target/'stage-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
