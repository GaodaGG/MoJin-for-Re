"""Compare the recorded controlled-training movement and input edges at 60/120.

This checks a measured transform and elapsed time, not all combat systems.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]

def value(row, key):
    return struct.unpack('<f', int(row[key],16).to_bytes(4,'little'))[0]

def read(run):
    meta=json.loads((run/'run.json').read_text())
    assert meta['exit_code']==0 and not meta['timed_out']
    rows=[r for r in csv.DictReader((run/'loop.csv').open()) if r['pc']=='0891d368']
    samples=[r for r in rows if 7600<=int(r['vcount'])<=8800]
    assert samples and all(r['transform_valid']=='1' for r in samples)
    edges=[(int(r['vcount']),int(r['input_pressed'])) for r in samples if int(r['input_pressed'])]
    expected=[(7620,32),(7800,128),(7980,16384),(8160,32768),(8340,4096),
              (8520,8192),(8700,32768),(8730,32768),(8760,32768)]
    assert len(edges)==len(expected)
    assert all(mask==em and 0<=v-ev<=3 for (v,mask),(ev,em) in zip(edges,expected)),edges
    segments={}
    for name,start,end in [('run_right',7618,7700),('run_left',7798,7880),
                           ('guard',7978,8100),('light_attack',8158,8300),
                           ('heavy_attack',8338,8480),('ability',8518,8660),
                           ('combo',8698,8800)]:
        segment=[r for r in rows if start<=int(r['vcount'])<=end]
        assert int(segment[0]['vcount'])<=start+1 and int(segment[-1]['vcount'])>=end-1
        distances=[]
        for a,b in itertools.pairwise(segment):
            distances.append(math.dist([value(a,k) for k in ('transform_x','transform_z','transform_y')],
                                       [value(b,k) for k in ('transform_x','transform_z','transform_y')]))
        moving=[i for i,d in enumerate(distances) if d>0.00001]
        segments[name]=dict(path_length=sum(distances),samples=len(segment),
            start=[value(segment[0],k) for k in ('transform_x','transform_z','transform_y')],
            finish=[value(segment[-1],k) for k in ('transform_x','transform_z','transform_y')],
            movement_seconds=(int(segment[moving[-1]+1]['guest_us'])-int(segment[moving[0]]['guest_us']))/1e6 if moving else 0,
            maximum_height=max(value(r,'transform_y') for r in segment))
    return dict(run=str(run.relative_to(ROOT)),executable_sha256=meta['executable_sha256'],
                input_sha256=meta['input_script_sha256'],edges=edges,segments=segments,
                evidence={p:hashlib.sha256((run/p).read_bytes()).hexdigest() for p in ('run.json','loop.csv','input.pad')})

def main():
    p=argparse.ArgumentParser(); p.add_argument('baseline',type=Path); p.add_argument('high',type=Path)
    args=p.parse_args(); a,b=read(args.baseline.resolve()),read(args.high.resolve())
    assert a['executable_sha256']==b['executable_sha256'] and a['input_sha256']==b['input_sha256']
    comparisons={}
    for name in ('run_right','run_left','light_attack','heavy_attack'):
        x,y=a['segments'][name],b['segments'][name]
        ratio=y['path_length']/x['path_length']
        duration_delta=y['movement_seconds']-x['movement_seconds']
        comparisons[name]=dict(distance_ratio=ratio,duration_delta_seconds=duration_delta,
            strict_distance_within_five_percent=0.95<=ratio<=1.05,
            duration_within_one_original_frame=abs(duration_delta)<=1/60)
    timing=all(x['duration_within_one_original_frame'] for x in comparisons.values())
    distance=all(x['strict_distance_within_five_percent'] for x in comparisons.values())
    result=dict(timing_comparison_passed=timing,strict_distance_comparison_passed=distance,
        baseline=a,high=b,comparisons=comparisons,
        scope='Same controlled training fighter, measured transform, two one-second runs and two attacks; input edges exactly once.',
        limitations=['The strict five-percent displacement check is retained and reported independently; a timing pass does not override a distance failure.',
                     'Does not certify every character, effect, physics interaction or ability cooldown.',
                     'Compare animation and hit effects against the separately retained rendered captures.',
                     'Transform fields are version-bound observations, not a public mod API.'])
    out=ROOT/'development/evidence/120fps-motion-test.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'timing_comparison_passed':timing,'strict_distance_comparison_passed':distance,
                      'report':str(out),'comparisons':comparisons},indent=2))
    if not timing: raise SystemExit(1)

if __name__=='__main__': main()
