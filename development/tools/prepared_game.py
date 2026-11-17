"""Freeze and verify title-derived C inputs for builds that never open an ISO.

This is a local build-input format, not a redistribution permission or a cache.
The manifest records exact content and generator provenance. Changing lowering
requires regeneration from the original program before exporting another set.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT/'development'
PREPARED = DEV/'prepared/game'
REV = '2263985dd8882acbbf1a7313f3752979e7f88e2d'
ISO_SHA = '40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb'
IMAGE_SHA = 'aa17cb3f96155592be82a9a0629ec876b61169e3dd3e7ab4e5d8b5e6da53d2f4'
DISC_SHA = '4964a21dc82750ffeab9dc082af3e92c65b630f09f3dc484da63a49378ee7cc2'
NAMES = {'mojin_recomp.c', 'mojin_recomp_funcs.h', 'mojin_recomp_opt.mk',
         'mojin_image.bin', 'mojin_imports.toml', 'mojin_recomp_coverage.json',
         'mojin_recomp_stubs.txt'} | {f'mojin_recomp_{i}.c' for i in range(126)}
GENERATOR_INPUTS = ('development/tools/codegen.py', 'development/tools/entry_proof.py',
                    'development/inputs/dispatch-seeds.txt')

def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def verify(folder=PREPARED, *, check_generator=True):
    folder = Path(folder)
    meta = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert meta['schema'] == 1 and meta['source_revision'] == REV
    assert meta['input_iso_sha256'] == ISO_SHA and meta['resource_manifest_sha256'] == DISC_SHA
    assert sha(DEV/'assets/disc-manifest.json') == DISC_SHA, 'Wrong resource version'
    assert set(meta['files']) == NAMES, 'Incomplete or unexpected prepared input set'
    assert {p.name for p in folder.iterdir()} == NAMES | {'manifest.json'}, 'Unexpected prepared payload'
    for name, row in meta['files'].items():
        path = folder/name
        assert path.is_file() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], name
    assert meta['files']['mojin_image.bin']['sha256'] == IMAGE_SHA
    assert set(meta['generator_inputs']) == set(GENERATOR_INPUTS)
    if check_generator:
        for name, expected in meta['generator_inputs'].items():
            assert sha(ROOT/name) == expected, f'Generator input changed; regenerate prepared C: {name}'
    return meta

def stage():
    meta = verify()
    dest = DEV/'generated/baseline'
    dest.mkdir(parents=True, exist_ok=True)
    for name, row in meta['files'].items():
        target = dest/name
        if target.exists():
            assert sha(target) == row['sha256'], f'Preserve changed generated input: {target}'
        else:
            shutil.copyfile(PREPARED/name, target)
            assert sha(target) == row['sha256']
    unexpected = {p.name for p in dest.glob('mojin_recomp*.c')} - NAMES
    assert not unexpected, f'Unexpected generated compilation units: {unexpected}'
    return dict(mode='prepared-c', manifest='development/prepared/game/manifest.json',
                manifest_sha256=sha(PREPARED/'manifest.json'), files=meta['files'],
                iso_opened=False, elf_opened=False)

def verify_staged(provenance):
    meta = verify()
    assert sha(PREPARED/'manifest.json') == provenance['manifest_sha256']
    assert meta['files'] == provenance['files']
    dest = DEV/'generated/baseline'
    for name, row in meta['files'].items(): assert sha(dest/name) == row['sha256'], name
    assert {p.name for p in dest.glob('mojin_recomp*.c')} == {n for n in NAMES if n.endswith('.c')}

def export(build_path):
    build_path = build_path.resolve()
    assert build_path.is_relative_to(DEV), 'Use a local verified build'
    build = json.loads(build_path.read_text(encoding='utf-8'))
    assert build['source_revision'] == REV and build['input_iso_sha256'] == ISO_SHA
    assert build['image_sha256'] == IMAGE_SHA
    source_root = build_path.parents[3]
    generator = {name:build['local_build_inputs'][name] for name in GENERATOR_INPUTS}
    for name, expected in generator.items():
        assert sha(source_root/name) == expected and sha(ROOT/name) == expected, name
    assert sha(source_root/'development/assets/disc-manifest.json') == DISC_SHA
    source = build_path.parent
    assert sha(source/'mojin_image.bin') == IMAGE_SHA
    assert {p.name for p in source.glob('mojin_recomp*.c')} == {n for n in NAMES if n.endswith('.c')}
    assert not PREPARED.exists() or not any(PREPARED.iterdir()), 'Use an empty prepared input directory'
    PREPARED.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name in sorted(NAMES):
        shutil.copyfile(source/name, PREPARED/name)
        rows[name] = dict(bytes=(source/name).stat().st_size, sha256=sha(source/name))
        assert sha(PREPARED/name) == rows[name]['sha256']
    meta = dict(schema=1, source_revision=REV, input_iso_sha256=ISO_SHA,
                resource_manifest_sha256=DISC_SHA, generator_inputs=generator, files=rows,
                source_build_sha256=sha(build_path), source_executable_sha256=build['executable_sha256'],
                notice='Derived game code and data. This manifest grants no redistribution rights.')
    (PREPARED/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
    verify()
    print(json.dumps(dict(files=len(rows),bytes=sum(x['bytes'] for x in rows.values()),
                         manifest_sha256=sha(PREPARED/'manifest.json')),indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['export','verify'])
    parser.add_argument('--build', type=Path)
    args=parser.parse_args()
    if args.action == 'export':
        if args.build is None: parser.error('export requires --build <verified .build.json>')
        export(args.build)
    else:
        result=verify(); print(f"Verified {len(result['files'])} prepared inputs; ISO not opened.")
