"""Restore/verify the pinned public source from its fixed release archive.

No network, generated game code, old objects or executable is a source input.
A Git checkout keeps the existing pinned-commit contract. An archive restore
must match every shipped source byte and the fixed archive SHA, not a receipt
which the candidate could rewrite to attest itself.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'
SRC=DEV/'third_party/nakagawa'
ARCHIVE=DEV/'downloads/nakagawa-recomp-0.0.3-windows-x64.zip'
ARCHIVE_SHA='af52764c7f25d55759cc05545aeb7bc7a6ca1f51aa223dc4ddb47d7bff760a0d'
REV='2263985dd8882acbbf1a7313f3752979e7f88e2d'


def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def source_archive(restore=False):
    assert sha(ARCHIVE)==ARCHIVE_SHA, 'Pinned upstream release changed'
    rows={}
    with zipfile.ZipFile(ARCHIVE) as z:
        assert ('Commit:     '+REV) in z.read('SOURCE.txt').decode('utf-8')
        for item in z.infolist():
            if not item.filename.startswith('source/') or item.is_dir(): continue
            relative=PurePosixPath(item.filename).relative_to('source')
            assert not relative.is_absolute() and '..' not in relative.parts and not any(':' in p for p in relative.parts)
            target=SRC.joinpath(*relative.parts)
            assert target.resolve().is_relative_to(SRC.resolve())
            data=z.read(item); digest=hashlib.sha256(data).hexdigest()
            if restore and not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as f: f.write(data)
            assert target.is_file() and sha(target)==digest, f'Missing/changed source; preserve it: {target}'
            rows[relative.as_posix()]=dict(sha256=digest,bytes=len(data))
    assert len(rows)==2001
    # Compile/generator inputs outside the release must not influence a restore.
    source_suffixes={'.c','.h','.cpp','.hpp','.inc','.py','.mk','.rc','.glsl','.vert','.frag'}
    for p in SRC.rglob('*'):
        if p.is_file() and p.suffix in source_suffixes:
            assert p.relative_to(SRC).as_posix() in rows, f'Unexpected source input: {p}'
    return dict(revision=REV,mode='fixed-release-source',archive_sha256=ARCHIVE_SHA,files=rows)


def verify():
    if (SRC/'.git').exists():
        rev=subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip()
        assert rev==REV, 'Unvalidated upstream revision'
        changed=subprocess.check_output(['git','-C',str(SRC),'status','--porcelain','--untracked-files=no'],text=True)
        assert not changed, 'Pinned upstream tracked source was changed; use project overlays'
        return dict(revision=rev,mode='pinned-git-clean')
    return source_archive()


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['restore','verify'])
    args=p.parse_args()
    result=source_archive(restore=True) if args.action=='restore' else verify()
    if args.action=='restore':
        (DEV/'evidence').mkdir(parents=True,exist_ok=True)
        (DEV/'evidence/upstream-source-restore.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(revision=result['revision'],mode=result['mode'],files=len(result.get('files',{}))),indent=2))
