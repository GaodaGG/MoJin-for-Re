"""Build from frozen project source, raw ISO and pinned release prerequisites.

The target starts without ELF, generated C/image, objects, binaries or caches.
The release archive is the authority for every restored dependency. Identical
tool/resource payloads may share regular hardlinks after byte-hash comparison;
old generated output is never restored or used as a build input.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'


def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(); p.add_argument('destination',type=Path)
    p.add_argument('--source-archive',type=Path,required=True)
    args=p.parse_args(); dest=args.destination.resolve(); source=args.source_archive.resolve()
    assert dest.is_relative_to(DEV/'rebuild') and dest!=DEV/'rebuild'
    assert not dest.exists() or not any(dest.iterdir()), 'Rebuild target must be empty'
    assert source.is_relative_to(ROOT/'archive')
    dest.mkdir(parents=True,exist_ok=True)
    for name in ('evidence','inputs','downloads'):
        (dest/'development'/name).mkdir(parents=True,exist_ok=True)
    restored={}
    with zipfile.ZipFile(source) as z:
        manifest=json.loads(z.read('restore-manifest.json'))
        # Code/configuration/assets only. Exclude the old package and evidence.
        for name,row in manifest.items():
            if not (name.startswith(('development/tools/','development/runtime/','development/assets/','development/inputs/')) or
                    name in ('development/mojin.mk','README.md','CONTINUE.md','development/DEVELOPMENT.md')): continue
            assert not name.endswith(('.exe','.dll','.o','.elf'))
            target=(dest/name).resolve(); assert target.is_relative_to(dest)
            data=z.read(name); assert hashlib.sha256(data).hexdigest()==row['sha256']
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
            restored[name]=row['sha256']
    # Freeze this turn's explicit recovery changes, recording each exact delta.
    updates={}
    for name in ('build.py','upstream_source.py','bootstrap_toolchain.py','disc_data.py','clean_rebuild.py','probe.py','program_abi.py'):
        src=DEV/'tools'/name; rel='development/tools/'+name; data=src.read_bytes()
        (dest/rel).write_bytes(data)
        updates[rel]=dict(before=restored.get(rel),after=sha(src))
        restored[rel]=sha(src)
    pad=DEV/'tests/vs-cpu-entry.pad'
    target_pad=dest/'development/tests/vs-cpu-entry.pad'
    target_pad.parent.mkdir(parents=True,exist_ok=True)
    target_pad.write_bytes(pad.read_bytes())
    for name in ('魔法禁书目录.iso','development/downloads/nakagawa-recomp-0.0.3-windows-x64.zip'):
        os.link(ROOT/name,dest/name)
    env={k:v for k,v in os.environ.items() if not k.startswith(('SR_','PSP_','NK_','GAME_','CMAKE_')) and k not in
         ('CC','CXX','CFLAGS','CXXFLAGS','LDFLAGS','LIB','INCLUDE','LIBRARY_PATH','CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','PYTHONPATH','VULKAN_SDK','SDL3_DIR')}
    # Bootstrap has only the host Python + Windows utilities. Native build adds
    # the newly verified local tool tree itself; no original development PATH.
    system=Path(os.environ['SystemRoot'])
    env['PATH']=os.pathsep.join(str(p) for p in (system/'System32',system,system/'System32/WindowsPowerShell/v1.0'))
    env['PYTHONIOENCODING']='utf-8'; env['PYTHONNOUSERSITE']='1'
    record=dict(started_utc=datetime.now(timezone.utc).isoformat(),root=str(dest),
                source_archive=str(source),source_archive_sha256=sha(source),project_sources=restored,
                recovery_source_updates=updates,raw_iso_sha256=sha(dest/'魔法禁书目录.iso'),
                dependency_archive_sha256=sha(dest/'development/downloads/nakagawa-recomp-0.0.3-windows-x64.zip'),
                host_python=sys.executable,host_python_version=sys.version,bootstrap_path=env['PATH'],
                acceptance_input_scripts={'development/tests/vs-cpu-entry.pad':sha(pad)},
                stages=[],prior_generated_inputs_used=False)
    report=dest/'rebuild.json'
    def save(): report.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def stage(name,argv):
        logfile=dest/'development/evidence'/f'rebuild-{name}.log'
        row=dict(name=name,command=argv,log=str(logfile.relative_to(dest)),started_utc=datetime.now(timezone.utc).isoformat())
        record['stages'].append(row); save(); print('Starting '+name,flush=True)
        with logfile.open('w',encoding='utf-8') as out:
            process=subprocess.Popen(argv,cwd=dest,env=env,stdout=out,stderr=subprocess.STDOUT)
            row['pid']=process.pid; save()
            row['exit_code']=process.wait()
        row['log_sha256']=sha(logfile); save()
        print(f"{name}: exit {row['exit_code']}",flush=True)
        if row['exit_code']:
            record['status']='FAILED_STAGE'; record['failed_stage']=name; save()
            print('\n'.join(logfile.read_text(encoding='utf-8',errors='replace').splitlines()[-24:])); raise SystemExit(row['exit_code'])
    stage('public-source',[sys.executable,str(dest/'development/tools/upstream_source.py'),'restore'])
    stage('toolchain',[sys.executable,str(dest/'development/tools/bootstrap_toolchain.py'),'--reuse-verified',str(DEV/'toolchain')])
    stage('resources',[sys.executable,str(dest/'development/tools/disc_data.py'),'extract','--reuse-verified',str(DEV/'resources/game')])
    assert not (dest/'development/inputs/EBOOT.elf').exists()
    assert not (dest/'development/generated/baseline').exists()
    assert not (dest/'development/build').exists()
    record['clean_before_compile']=True; save()
    # Re-run the full pipeline with the restored fixed portable Python.
    py=dest/'development/toolchain/python/python.exe'
    stage('all',[str(py),str(dest/'development/tools/build.py'),'all','--output-name','mojin-rebuilt.exe'])
    generated=dest/'development/generated/baseline'
    build=json.loads((generated/'mojin-rebuilt.build.json').read_text(encoding='utf-8'))
    record['result']=build
    record['generated_files']={f.name:sha(f) for f in generated.iterdir() if f.is_file() and
        (f.name.startswith('mojin_recomp') or f.name in ('mojin_image.bin','mojin_imports.toml'))}
    record['raw_iso_unchanged']=sha(dest/'魔法禁书目录.iso')==record['raw_iso_sha256']
    record['status']='COMPILED_NOT_RUNTIME_ACCEPTED'; save()
    print(json.dumps(dict(root=str(dest),status=record['status'],executable_sha256=build['executable_sha256']),indent=2))


if __name__=='__main__': main()
