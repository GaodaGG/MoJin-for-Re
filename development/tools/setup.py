"""Fetch and verify fixed build dependencies; no ISO or game download needed."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parent))
ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'
URL='https://github.com/Jstar269/Nakagawa-Recomp/releases/download/v0.0.3/nakagawa-recomp-0.0.3-windows-x64.zip'
SHA='af52764c7f25d55759cc05545aeb7bc7a6ca1f51aa223dc4ddb47d7bff760a0d'

def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,help='Reuse an already downloaded archive after exact hash verification')
    parser.add_argument('--reuse-verified-toolchain',type=Path,help='Optional local storage sharing; each file is compared with the fixed archive')
    args=parser.parse_args()
    if sys.version_info<(3,11) or os.name!='nt':
        raise SystemExit('This bootstrap currently requires Windows and Python 3.11+; other platforms are untested.')
    for name in ('evidence','downloads','inputs','assets'):
        (DEV/name).mkdir(parents=True,exist_ok=True)
    from upstream_source import verify
    verify()  # requires the pinned initialized submodule or exact fixed-source restore
    archive=DEV/'downloads/nakagawa-recomp-0.0.3-windows-x64.zip'
    if not archive.exists():
        if args.archive:
            source=args.archive.resolve()
            assert sha(source)==SHA, 'Wrong dependency archive; no files installed'
            try: os.link(source,archive)
            except OSError:
                import shutil
                shutil.copyfile(source,archive)
        else:
            temporary=archive.with_suffix('.zip.download')
            print(f'Downloading fixed toolchain (276957044 bytes): {URL}',flush=True)
            with temporary.open('xb') as output, urllib.request.urlopen(URL,timeout=60) as response:
                while chunk:=response.read(1024*1024): output.write(chunk)
            assert sha(temporary)==SHA, 'Download hash mismatch; retained .download for diagnosis'
            temporary.rename(archive)
    assert sha(archive)==SHA, 'Existing archive differs; preserve it and investigate'
    command=[sys.executable,str(DEV/'tools/bootstrap_toolchain.py')]
    if args.reuse_verified_toolchain:
        command += ['--reuse-verified',str(args.reuse_verified_toolchain.resolve())]
    subprocess.run(command,cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(DEV/'tools/fetch_cjk_font.py')],cwd=ROOT,check=True)
    from prepared_game import verify as verify_game
    from disc_data import verify as verify_resources
    verify_game(); verify_resources()
    print('Dependencies and prepared inputs verified. Build: python development/tools/build.py prepared')

if __name__=='__main__': main()
