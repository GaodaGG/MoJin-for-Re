"""Build/package a fresh local snapshot while the original ISO is unreadable.

No old objects, native binaries, generated fonts, or raw ISO/ELF are restored.
Prepared game C/image and loose resources are explicitly the source inputs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'

def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('destination',type=Path)
    args=parser.parse_args(); dest=args.destination.resolve()
    assert dest.is_relative_to(DEV/'rebuild') and dest!=DEV/'rebuild'
    assert not dest.exists() or not any(dest.iterdir()), 'Use an empty target'
    from prepared_game import verify
    from disc_data import verify as verify_resources
    verify(); resources=verify_resources()
    dest.mkdir(parents=True,exist_ok=True)
    for name in ('evidence','inputs','downloads'):
        (dest/'development'/name).mkdir(parents=True,exist_ok=True)
    sources=[]
    for folder in ('tools','runtime','assets','prepared/game'):
        sources += [p for p in (DEV/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    sources += [DEV/'mojin.mk',DEV/'inputs/dispatch-seeds.txt',DEV/'tests/vs-cpu-entry.pad']
    sources += [ROOT/name for name in ('LICENSE','COPYRIGHT.md','AI_DISCLOSURE.md')]
    snapshot={}
    for source in sources:
        relative=source.relative_to(ROOT); target=dest/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target); assert sha(source)==sha(target)
        snapshot[relative.as_posix()]=sha(source)
    for entry in resources['entries']:
        if entry['directory']: continue
        relative=Path('development/resources/game')/entry['path']
        target=dest/relative; target.parent.mkdir(parents=True,exist_ok=True)
        os.link(ROOT/relative,target); assert sha(target)==entry['sha256']
    archive=Path('development/downloads/nakagawa-recomp-0.0.3-windows-x64.zip')
    os.link(ROOT/archive,dest/archive)
    assert not (dest/'魔法禁书目录.iso').exists()
    assert not (dest/'development/inputs/EBOOT.elf').exists()
    assert not (dest/'development/generated/baseline').exists()
    env={k:v for k,v in os.environ.items() if not k.startswith(('SR_','PSP_','NK_','GAME_','CMAKE_')) and k not in
         ('CC','CXX','CFLAGS','CXXFLAGS','LDFLAGS','LIB','INCLUDE','LIBRARY_PATH','CPATH','C_INCLUDE_PATH',
          'CPLUS_INCLUDE_PATH','PYTHONPATH','PYTHONHOME','GCC_EXEC_PREFIX','COMPILER_PATH','VULKAN_SDK','SDL3_DIR','MAKEFLAGS')}
    system=Path(os.environ['SystemRoot'])
    env['PATH']=os.pathsep.join(str(p) for p in (system/'System32',system,system/'System32/WindowsPowerShell/v1.0'))
    env['PYTHONIOENCODING']='utf-8'; env['PYTHONNOUSERSITE']='1'
    from iso_unavailable import hold_iso_unavailable
    iso_record,release=hold_iso_unavailable()
    record=dict(started_utc=datetime.now(timezone.utc).isoformat(),project_sources=snapshot,
                iso_unavailable=iso_record,iso_present_in_snapshot=False,elf_present_in_inputs=False,
                old_objects_or_exe_restored=False,stages=[],status='RUNNING')
    report=dest/'prepared-rebuild.json'
    def save(): report.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    def stage(name,command):
        log=dest/'development/evidence'/f'prepared-{name}.log'
        row=dict(name=name,command=command,log=log.relative_to(dest).as_posix())
        record['stages'].append(row); save(); print('Starting '+name,flush=True)
        with log.open('w',encoding='utf-8') as output:
            process=subprocess.Popen(command,cwd=dest,env=env,stdout=output,stderr=subprocess.STDOUT)
            row['pid']=process.pid; save(); row['exit_code']=process.wait()
        row['log_sha256']=sha(log); save(); print(f'{name}: exit {row["exit_code"]}',flush=True)
        if row['exit_code']:
            record['status']='FAILED_STAGE'; record['failed_stage']=name; save()
            print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-25:]))
            raise SystemExit(row['exit_code'])
    try:
        stage('source',[sys.executable,str(dest/'development/tools/upstream_source.py'),'restore'])
        stage('tools',[sys.executable,str(dest/'development/tools/bootstrap_toolchain.py'),'--reuse-verified',str(DEV/'toolchain')])
        py=dest/'development/toolchain/python/python.exe'
        stage('compile',[str(py),str(dest/'development/tools/build.py'),'prepared','--output-name','mojin-noiso.exe'])
        stage('package',[sys.executable,str(dest/'development/tools/package_preview.py'),
                         str(dest/'development/releases/0.1.2-noiso-build'),'--exe','mojin-noiso.exe'])
        assert not (dest/'魔法禁书目录.iso').exists() and not (dest/'development/inputs/EBOOT.elf').exists()
        record['build']=json.loads((dest/'development/generated/baseline/mojin-noiso.build.json').read_text())
        assert record['build']['game_input']['mode']=='prepared-c'
        assert all(sha(dest/name)==digest for name,digest in snapshot.items())
        record['sources_unchanged']=True; record['status']='PACKAGED_NOT_RUNTIME_ACCEPTED'; save()
        print(json.dumps(dict(root=str(dest),status=record['status'],exe_sha256=record['build']['executable_sha256']),indent=2))
    finally: release()

if __name__=='__main__': main()
