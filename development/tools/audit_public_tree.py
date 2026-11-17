"""Audit the staged source tree, LFS payloads, submodule pin and private exclusions."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    rows=git('ls-files','--stage','-z').split(b'\0')
    entries=[]; blobs={}; lfs=[]; submodules=[]
    secrets=[re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
             re.compile(rb'github_pat_[A-Za-z0-9_]{30,}'),
             re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
             re.compile(rb'[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+[\\/]')]
    forbidden_prefixes=('archive/','play/','Switch','development/rebuild/','development/evidence/',
                        'development/generated/','development/releases/','development/toolchain/',
                        'development/downloads/','development/tests/runs/','development/tests/standalone/')
    forbidden_suffixes=('.iso','.cso','.pbp','.exe','.dll','.elf','.o','.d','.zip','.7z','.wav','.ppm','.bmp','.ngef','.pyc')
    for raw in rows:
        if not raw: continue
        header,name=raw.split(b'\t',1); mode,oid,stage=header.decode().split()
        name=name.decode('utf-8'); assert stage=='0'
        assert not name.startswith(forbidden_prefixes) and not name.lower().endswith(forbidden_suffixes),name
        assert '/SAVEDATA/' not in name and not name.endswith(('.env','.pem','.key')),name
        if mode=='160000':
            assert name=='development/third_party/nakagawa'
            assert oid=='2263985dd8882acbbf1a7313f3752979e7f88e2d'
            submodules.append(dict(path=name,revision=oid)); continue
        assert mode=='100644', (name,mode)
        if oid not in blobs: blobs[oid]=git('cat-file','blob',oid)
        data=blobs[oid]
        assert len(data)<10*1024*1024, f'Unreviewed large ordinary Git blob: {name}'
        is_lfs=data.startswith(b'version https://git-lfs.github.com/spec/v1\n')
        if name.startswith('development/resources/game/') or name=='development/prepared/game/mojin_image.bin':
            assert is_lfs, f'Expected LFS payload: {name}'
        if is_lfs:
            match=re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n',data)
            assert match,name
            digest=match[1].decode(); size=int(match[2]); actual=ROOT/name
            assert actual.stat().st_size==size and sha(actual)==digest,name
            lfs.append(dict(path=name,sha256=digest,bytes=size))
        else:
            assert (ROOT/name).read_bytes()==data, f'Index/worktree bytes differ: {name}'
            for pattern in secrets: assert not pattern.search(data), f'Potential private content: {name}'
            if name!='development/assets/game.ico':
                data.decode('utf-8')
        entries.append(dict(path=name,git_blob=oid,bytes=len(data)))
    assert len(submodules)==1
    assert len(lfs)==23, f'Expected 22 resource paths plus relocated image: {len(lfs)}'
    from prepared_game import verify
    from disc_data import verify as verify_resources
    verify(); verify_resources()
    tracked={e['path'] for e in entries}
    assert {'LICENSE','COPYRIGHT.md','AI_DISCLOSURE.md','README.md','.gitattributes','.gitmodules'}<=tracked
    assert {str(p.relative_to(ROOT)).replace('\\','/') for p in (DEV/'prepared/game').iterdir()}<=tracked
    # No game/secret exclusions should depend on a broad git add being careful.
    excluded=['魔法禁书目录.iso','play/MoJin.exe','CONTINUE.md','development/github_publish.py',
              'development/inputs/EBOOT.elf','development/evidence/disk-usage.json']
    for name in excluded:
        assert subprocess.run(['git','check-ignore','-q','--',name],cwd=ROOT).returncode==0,name
    result=dict(passed=True,staged_files=len(entries),git_blob_bytes=sum(e['bytes'] for e in entries),
                submodules=submodules,lfs=lfs,entries=entries,iso_and_private_paths_excluded=True,
                tree=git('write-tree').decode().strip())
    (DEV/'evidence/public-source-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','staged_files','git_blob_bytes','submodules','tree')},indent=2))

if __name__=='__main__': main()
