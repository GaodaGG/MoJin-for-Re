"""Identical captured GE commands, fresh app caches, prep on/off/partial.

Checks actual pixels and issued draw/primitive counts, not only pipeline totals.
This is a graphics fixture test, not game CPU or PSP-hardware acceptance.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('fixture',type=Path)
    args=parser.parse_args()
    fixture=args.fixture.resolve()
    assert fixture.is_relative_to(DEV/'tests/runs') and fixture.name=='frame.ngef'
    exe=DEV/'generated/ge-replay/ge_replay.exe'
    build=json.loads(exe.with_suffix('.build.json').read_text(encoding='utf-8'))
    assert sha(exe)==build['executable_sha256']
    out=DEV/'tests/graphics-replay'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir()
    record=dict(kind='Pipeline preparation equivalence',fixture=str(fixture.relative_to(ROOT)),
                fixture_sha256=sha(fixture),build=build,cases=[],
                boundaries=['Same captured GE commands, no game CPU execution or PSP hardware comparison.',
                            'All application caches start empty; driver-wide cache is not cleared.',
                            'Export is 480x272 guest VRAM, even at 4x/8x scene rendering.'])
    for scale in (1,4,8):
        reference=None
        for mode in ('off','on','partial'):
            case=out/f'{scale}x-{mode}'; case.mkdir()
            env={k:v for k,v in os.environ.items() if not k.startswith(('SR_','PSP_'))}
            env.update(PATH=str(DEV/'toolchain/msys64/ucrt64/bin')+os.pathsep+env['PATH'],
                SR_RESOLUTION_SCALE=str(scale),SR_WINDOW_HIDDEN='1',SR_GPU_STATS='1',
                SR_USER_DATA_ROOT=str(case/'user'),SR_MOJIN_WINDOW_PUMP='cooperative',
                SR_MOJIN_PREPARE='0' if mode=='off' else '1',
                SR_MOJIN_TTF_LIBRARY=str(DEV/'toolchain/msys64/ucrt64/bin/SDL3_ttf.dll'),
                SR_MOJIN_CJK_FONT=str(DEV/'assets/fonts/ui/noto-sans-sc/NotoSansCJKsc-Regular.otf'),
                SR_MOJIN_PIPELINE_TRACE=str(case/'pipelines.jsonl'),
                PSP_VFPU_TABLES=str(DEV/'third_party/nakagawa/assets/vfpu'))
            if mode=='partial': env['SR_MOJIN_PREP_LIMIT']='1'
            command=[str(exe),str(fixture),'--backend','vulkan','--output',str(case/'frame.ppm')]
            with (case/'stdout.log').open('wb') as stdout,(case/'stderr.log').open('wb') as stderr:
                result=subprocess.run(command,cwd=case,env=env,stdout=stdout,stderr=stderr,timeout=60,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode==0,case
            stdout=(case/'stdout.log').read_text(encoding='utf-8',errors='replace')
            stderr=(case/'stderr.log').read_text(encoding='utf-8',errors='replace')
            rows=[json.loads(x) for x in (case/'pipelines.jsonl').read_text().splitlines()]
            assert all(x['result']==0 for x in rows)
            assert 'started empty, saved' in stderr
            replay=re.search(r'^GE_REPLAY .*',stdout,re.M)[0]
            stats=re.search(r'^GEGPU stats: .*final=1',stderr,re.M)[0]
            counts={k:int(re.search(r'\b'+k+r'=(\d+)',replay)[1]) for k in ('lists','batches','draws')}
            counts.update({k:int(re.search(r'\b'+k+r'=(\d+)',stats)[1]) for k in ('verts','tris','spr','lines','nonfinite')})
            checksum=sha(case/'frame.ppm')
            if reference is None: reference=(checksum,counts)
            assert (checksum,counts)==reference,f'Output/draws changed: {case}'
            phases={phase:sum(r['phase']==phase for r in rows) for phase in ('preparation','draw')}
            if mode=='off': assert phases['preparation']==0 and phases['draw']>0
            if mode=='on': assert phases['preparation']==9
            if mode=='partial': assert phases['preparation']==1 and phases['draw']>0
            record['cases'].append(dict(case=case.name,exit_code=0,output_sha256=checksum,counts=counts,
                                       phases=phases,command=command,environment={k:v for k,v in env.items() if k.startswith(('SR_','PSP_'))}))
            (out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(dict(case=case.name,equal_pixels=True,equal_draw_counts=True,phases=phases)),flush=True)
    record['all_passed']=True
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (DEV/'evidence/pipeline-preparation-equivalence-test.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(out,flush=True)


if __name__=='__main__': main()
