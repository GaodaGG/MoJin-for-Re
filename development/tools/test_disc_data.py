"""Compile the actual backend; compare every resource byte with pinned hashes.

Also exercise the guest path/LBA ABI, concurrent reads and fail-closed bounds.
No GPU or title instruction execution is replaced by this component check.
"""
import ctypes as c
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from disc_data import DATA, DEV, ROOT, MANIFEST, manifest, prepare, sha, verify


def load(path):
    lib=c.CDLL(str(path))
    lib.iso_lookup.argtypes=[c.c_char_p,c.POINTER(c.c_uint32),c.POINTER(c.c_uint32)]
    lib.iso_read.argtypes=[c.c_uint32,c.c_uint32,c.c_void_p,c.c_uint32]
    lib.iso_list.argtypes=[c.c_char_p,c.c_uint32,c.c_void_p]
    lib.iso_sector_extent_path.argtypes=[c.c_char_p,c.c_void_p,c.c_size_t]
    return lib


def main():
    if len(sys.argv)>1:
        assert load(Path(sys.argv[1])).iso_init()==-1
        return
    prepare(); m=verify()
    run=DEV/'tests/disc-data'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    stub=run/'perf_stub.c'
    stub.write_text('#include "perf.h"\nint sr_perf_enabled=0;\nuint64_t sr_perf_now_ns_impl(void){return 0;}\n'
                    'void sr_perf_storage_read(SrPerfStorageSource s,uint32_t b,uint64_t t,int ok){(void)s;(void)b;(void)t;(void)ok;}\n',encoding='ascii')
    compiler=DEV/'toolchain/msys64/ucrt64/bin/gcc.exe'
    os.environ['PATH']=str(compiler.parent)+os.pathsep+os.environ['PATH']
    dll=run/'disc_test.dll'
    command=[str(compiler),'-shared','-O1','-Wall','-Wextra','-Werror','-I'+str(DEV/'third_party/nakagawa/src/rt'),
             str(DEV/'runtime/disc_data.c'),str(stub),'-o',str(dll)]
    subprocess.run(command,check=True)
    env=os.environ.copy(); env.pop('PSP_ISO',None); env['SR_MOJIN_GAME_DATA']=str(run/'absent')
    negative=subprocess.run([sys.executable,__file__,str(dll)],env=env,capture_output=True,text=True)
    assert negative.returncode==0, negative.stderr
    os.environ['SR_MOJIN_GAME_DATA']=str(DATA); os.environ.pop('PSP_ISO',None)
    lib=load(dll); assert lib.iso_init()==0
    class Entry(c.Structure):
        _fields_=[('name',c.c_char*256),('lba',c.c_uint32),('size',c.c_uint32),('is_dir',c.c_int),('is_symlink',c.c_int)]
    files=[e for e in m['entries'] if not e['directory']]
    def lookup(path):
        a,b=c.c_uint32(),c.c_uint32()
        rc=lib.iso_lookup(path.encode(),c.byref(a),c.byref(b))
        return rc,a.value,b.value
    def read(e,off,n):
        buf=c.create_string_buffer(n)
        assert lib.iso_read(e['lba'],off,buf,n)==n
        return buf.raw
    total=0
    for e in files:
        assert lookup('disc0:/'+e['path'].lower())==(0,e['lba'],e['size'])
        assert lookup('umd0:\\.\\'+e['path'].replace('/','\\'))==(0,e['lba'],e['size'])
        raw=f"disc0:/sce_lbn0x{e['lba']:x}_size0x{e['size']:x}"
        assert lookup(raw)==(0,e['lba'],e['size'])
        out=c.create_string_buffer(128)
        assert lib.iso_sector_extent_path(raw.encode(),out,128)==1 and out.value==raw.encode()
        digest=hashlib.sha256()
        for off in range(0,e['size'],65536):
            data=read(e,off,min(65536,e['size']-off)); digest.update(data); total+=len(data)
        assert digest.hexdigest()==e['sha256']
        assert lookup('disc0:/'+e['path']+'/')[0]==-1
    for directory in ['']+[e['path'] for e in m['entries'] if e['directory']]:
        children=[e for e in m['entries'] if e['path'].rpartition('/')[0]==directory]
        for i,e in enumerate(children):
            out=Entry(); assert lib.iso_list(('disc0:/'+directory.lower()).encode(),i,c.byref(out))==1
            assert out.name.decode()==e['path'].split('/')[-1] and out.lba==e['lba'] and out.is_dir==e['directory']
            assert out.size==(0 if e['directory'] else e['size']) and not out.is_symlink
        assert lib.iso_list(('disc0:/'+directory).encode(),len(children),c.byref(Entry()))==0
    rng=random.Random(329)
    cases=[]
    for _ in range(200):
        e=rng.choice(files); off=rng.randrange(e['size']); n=min(1021,e['size']-off)
        with (DATA/e['path']).open('rb') as f: f.seek(off); expected=f.read(n)
        cases.append((e,off,n,expected))
    def concurrent(case):
        e,off,n,expected=case
        assert read(e,off,n)==expected
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(concurrent,cases))
    for invalid in ['disc0:/PSP_GAME/../UMD_DATA.BIN','disc0:/PSP_GAME','disc0:/absent',
                    'disc0:/sce_lbn0_size800','disc0:/sce_lbnffffffff_sizeffffffff',
                    'disc0:/sce_lbn0x1_size0x0','disc0:/sce_lbn0x1_size0x20junk']:
        assert lookup(invalid)[0]==-1,invalid
    buf=c.create_string_buffer(2048)
    assert lib.iso_read(0,0,buf,2048)==-1
    assert lib.iso_read(0xffffffff,0xffffffff,buf,2048)==-1
    assert lib.iso_read(28,0,buf,49)==-1  # one byte beyond UMD_DATA; no fabricated padding
    sectors=c.c_uint32(); assert lib.iso_sector_count(c.byref(sectors))==0 and sectors.value==m['physical_bytes']//2048
    record=dict(all_passed=True,files=len(files),bytes_compared=total,concurrent_reads=len(cases),
                missing_root_rejected=True,unmapped_reads_rejected=True,iso_environment=False,
                backend_sha256=sha(DEV/'runtime/disc_data.c'),manifest_sha256=sha(MANIFEST),
                component_library_sha256=sha(dll),command=command)
    (run/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (DEV/'evidence/disc-data-test.json').write_text(json.dumps(dict(record,run=str(run)),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__': main()
