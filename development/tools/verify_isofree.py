"""Bind ISO-denied movie/battle/no-argument acceptance to the shipped executable."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from disc_data import ROOT, DEV, MANIFEST, verify, sha


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('package',type=Path); p.add_argument('battle',type=Path); p.add_argument('movies',type=Path)
    p.add_argument('--launch',type=Path,help='No-argument evidence from an independently staged copy of the same executable')
    args=p.parse_args(); package=args.package.resolve()
    release=read(package/'release-manifest.json'); digest=sha(package/'MoJin.exe')
    assert release['iso_external'] is False and release['build']['executable_sha256']==digest
    verify(package/'data/game')
    for name,info in release['files'].items():
        f=package/name
        assert f.is_file() and not f.is_symlink() and sha(f)==info['sha256'],name
        assert all(not parent.is_junction() for parent in [f.parent,*f.parents] if parent.is_relative_to(package))
    launch_path=args.launch or package/'standalone-test.json'
    launch=read(launch_path)
    assert launch['executable_sha256']==digest and launch['exit_code']==0 and launch['argc']==1
    assert not launch['path_has_toolchain'] and launch['visible_owned_window_titles']==['魔法禁书目录']
    assert launch['iso_unavailable']['second_open_error']==32
    launched_root=Path(launch['command'][0]).parent
    assert sha(launched_root/'MoJin.exe')==digest
    for name,info in release['files'].items():
        assert sha(launched_root/name)==info['sha256'],name
    records=[]
    for directory in [args.battle.resolve(),args.movies.resolve()]:
        meta=read(directory/'run.json'); log=(directory/'stderr.log').read_text(encoding='utf-8')
        assert meta['executable_sha256']==digest and meta['exit_code']==0 and not meta['timed_out']
        assert meta['iso_unavailable']['second_open_error']==32 and 'PSP_ISO' not in meta['environment']
        assert 'interp_entries=0 entries_dispatch_miss=0' in log and 'Guest requested exit (sceKernelExitGame())' in log
        counts=re.search(r'MOJIN_GAME_DATA reads=(\d+) bytes=(\d+) errors=(\d+) backend=files',log)
        assert counts and int(counts[1])>0 and int(counts[2])>0 and counts[3]=='0'
        audio=re.search(r'AUDIODUMP: .* frames=(\d+) seconds=([\d.]+).* dropped_frames=(\d+)',log)
        assert audio and int(audio[1])>0 and audio[3]=='0'
        records.append(dict(run=directory.relative_to(ROOT).as_posix(),pid=meta['pid'],seconds=meta['elapsed_seconds'],
                            reads=int(counts[1]),bytes=int(counts[2]),read_errors=0,audio_seconds=float(audio[2]),
                            evidence={name:sha(directory/name) for name in ('run.json','stderr.log','build.json')}))
    battle=read(args.battle/'run.json')
    assert battle['runtime_package']==str(package) and battle['path_has_toolchain'] is False
    reload=read(args.battle/'savedata-reload-verification.json'); assert reload['load_result']==0
    media=read(args.movies/'media-clock-verification.json')
    assert media['passed'] and media['full_movie_counters_checked']
    symbols=subprocess.check_output([str(DEV/'toolchain/msys64/ucrt64/bin/nm.exe'),str(package/'MoJin.exe')],text=True)
    assert ' T iso_read' in symbols and ' T iso_lookup' in symbols
    assert 'nk_iso_reader_' not in symbols
    assert sha(ROOT/'魔法禁书目录.iso')==release['build']['input_iso_sha256']
    result=dict(passed=True,version=release['version'],executable_sha256=digest,
                package=str(package),runtime_files_verified=len(release['files']),
                iso_unavailable_for_all_runs=True,iso_reader_symbols_absent=True,original_iso_unchanged=True,
                disc_manifest_sha256=sha(MANIFEST),component_check=read(DEV/'evidence/disc-data-test.json'),
                no_argument_launch=launch,runs=records,save_reload=reload,
                boundaries=['One vs CPU bridge route and complete AMW/OP, not full-game/story/progress save acceptance.',
                            'Initial game save loaded in a distinct process; user play data never used by tests.',
                            'Package loads from regular files with compiled LBA metadata; unmapped raw sector reads reject.',
                            'Audio output/counters checked, not device-loopback synchronization; Windows x64 only.'])
    assert result['component_check']['backend_sha256']==release['build']['local_build_inputs']['development/runtime/disc_data.c']
    output=DEV/'evidence/isofree-release-test.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,report=str(output),executable_sha256=digest,runs=records),indent=2))


if __name__=='__main__': main()
