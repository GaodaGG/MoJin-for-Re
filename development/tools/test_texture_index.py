"""Compile the actual texture index and compare it with linear lookup under eviction."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT/'development'

def main():
    output = DEV/'tests/texture-index'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True)
    upstream = (DEV/'third_party/nakagawa/src/rt/gpu_sdl3vk/ge_gpu.c').read_text()
    end = upstream.index('} TexMipKey;') + len('} TexMipKey;')
    mip = upstream[upstream.rfind('typedef struct {',0,end):end]
    source = output/'check.c'
    source.write_text('#include <stdint.h>\n#include <string.h>\n#include <stdlib.h>\n#include <assert.h>\n#include <stdio.h>\n'+mip+'''
typedef struct { uint64_t key; TexMipKey mip; unsigned payload; } TexEnt;
static TexEnt s_tex[1024];
static int s_tex_n;
#include "texture_index.h"
static uint32_t rng=329;
static uint32_t next(void) { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; }
static int find(uint64_t key, const TexMipKey *mip, int start) {
    for(int i=start;i<s_tex_n;i++)
        if(s_tex[i].key==key && !memcmp(&s_tex[i].mip,mip,sizeof(*mip))) return i;
    return -1;
}
int main(void) {
    unsigned hits=0,misses=0,evictions=0,mip_changes=0,shortcuts=0;
    for(unsigned round=0;round<100000;round++) {
        if(s_tex_n && round%31==0) {
            unsigned index=next()%(unsigned)s_tex_n;
            s_tex[index]=s_tex[--s_tex_n]; /* Same moving-slot eviction shape. */
            ++evictions;
        }
        if(s_tex_n && round%17==0) {
            unsigned index=next()%(unsigned)s_tex_n;
            ((unsigned char*)&s_tex[index].mip)[round%sizeof(TexMipKey)]^=1;
            ++mip_changes;
        }
        TexEnt query={0};
        if(s_tex_n && next()%5) query=s_tex[next()%(unsigned)s_tex_n];
        else {
            query.key=next()%128; /* Deliberate key collisions, mip distinguishes identities. */
            for(unsigned j=0;j<sizeof(TexMipKey);j++) ((unsigned char*)&query.mip)[j]=(unsigned char)next();
            query.payload=round;
        }
        int expected=find(query.key,&query.mip,0);
        int start=mojin_texture_start(query.key,&query.mip);
        int observed=find(query.key,&query.mip,start);
        assert(expected==observed);
        if(start) ++shortcuts;
        if(observed>=0) { ++hits; mojin_texture_found(query.key,(unsigned)observed); }
        else {
            ++misses;
            if(s_tex_n==1024) { s_tex[next()%1024]=s_tex[--s_tex_n]; ++evictions; }
            s_tex[s_tex_n]=query;
            mojin_texture_found(query.key,(unsigned)s_tex_n++);
        }
        if(round%1000==999) s_tex_n=0; /* Stale table across complete renderer resets. */
    }
    mojin_texture_index_enabled=0;
    TexMipKey empty={0};
    assert(mojin_texture_start(0,&empty)==0);
    assert(hits>70000 && misses>10000 && evictions>3000 && mip_changes>5000 && shortcuts>10000);
    printf("PASS lookups=100000 hits=%u misses=%u evictions=%u mip_changes=%u shortcuts=%u\\n",hits,misses,evictions,mip_changes,shortcuts);
    return 0;
}
''',encoding='utf-8')
    gcc=DEV/'toolchain/msys64/ucrt64/bin/gcc.exe'
    exe=output/'check.exe'
    command=[str(gcc),'-O3','-Wall','-Wextra','-Werror','-I'+str(DEV/'runtime'),str(source),'-o',str(exe)]
    env=dict(os.environ,PATH=str(gcc.parent)+os.pathsep+os.environ['PATH'])
    env.pop('SR_MOJIN_TEXTURE_LINEAR',None)
    subprocess.run(command,env=env,check=True)
    result=subprocess.run([str(exe)],env=env,check=True,text=True,capture_output=True)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record=dict(passed=True,output=result.stdout.strip(),command=command,
        header_sha256=digest(DEV/'runtime/texture_index.h'),test_source_sha256=digest(source),
        executable_sha256=digest(exe),limits=['Index equivalence only; actual renderer pixels and gameplay require separate checks.'])
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    (DEV/'evidence/texture-index-test.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    main()
