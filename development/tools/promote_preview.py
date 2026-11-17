"""Install a verified native preview without replacing user settings or saves.

Only changed manifest-owned files are replaced, using new files + os.replace.
Rollback bytes are verified in a ZIP and restored on disk before installation.
"""
import argparse
import atexit
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def safe_file(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base) or path == base:
        raise SystemExit(f'Unsafe manifest path: {name}')
    return path


def mutable(name):
    return name in ('settings.ini', 'settings.ini.previous') or name.split('/')[0] in ('saves', 'userdata', 'logs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--launch-evidence', type=Path, required=True)
    parser.add_argument('--icon-evidence', type=Path, required=True)
    args = parser.parse_args()
    package, source_archive = args.package.resolve(), args.source_archive.resolve()
    play = ROOT / 'play'
    if not package.is_relative_to(ROOT / 'development/releases') or not source_archive.is_relative_to(ROOT / 'archive'):
        parser.error('Use project release and archive paths')
    new = read_json(package / 'release-manifest.json')
    old = read_json(play / 'release-manifest.json')
    digest = new['files']['MoJin.exe']['sha256']
    launch, icon = read_json(args.launch_evidence), read_json(args.icon_evidence)
    assert launch['executable_sha256'] == icon['executable_sha256'] == digest
    assert launch['exit_code'] == 0 and launch['argc'] == 1 and not launch['path_has_toolchain']
    assert launch['visible_owned_window_titles'] == ['魔法禁书目录']
    assert icon['exact_image_payloads_match'] and icon['icon_images_verified'] == 7
    if new.get('iso_external') is False:
        independent = read_json(ROOT/'development/evidence/isofree-release-test.json')
        assert independent['passed'] and independent['executable_sha256'] == digest
        assert independent['iso_unavailable_for_all_runs'] and independent['iso_reader_symbols_absent']
    for name, info in new['files'].items():
        assert sha(safe_file(package, name).read_bytes()) == info['sha256'], name
    # Frozen matching source is authoritative; today's development tree may differ.
    with zipfile.ZipFile(source_archive) as z:
        assert z.testzip() is None
        archive_manifest = json.loads(z.read('restore-manifest.json'))
        for name, info in archive_manifest.items():
            assert sha(z.read(name)) == info['sha256'], name
        assert sha(z.read('play/MoJin.exe')) == digest
        for name, expected in new['build']['local_build_inputs'].items():
            assert sha(z.read(name)) == expected, name
    # Same lock as native startup: refuse to update a running user session.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    lock = kernel.CreateFileW(str(play/'.session.lock'),0xc0000000,0,None,4,0x04000100,None)
    if lock == ctypes.c_void_p(-1).value:
        raise SystemExit('Close the normal play game before installing; no process was stopped.')
    atexit.register(lambda: kernel.CloseHandle(lock))
    before = {p.relative_to(play).as_posix(): sha(p.read_bytes()) for p in play.rglob('*') if p.is_file() and p.name != '.session.lock'}
    for name, info in old['files'].items():
        if not mutable(name):
            assert before.get(name) == info['sha256'], f'Unexpected change in existing managed file: {name}'
    changed = [name for name, info in new['files'].items()
               if not mutable(name) and before.get(name) != info['sha256']]
    for name in changed:
        if name in before and name not in old['files']:
            raise SystemExit(f'Refusing to replace untracked file: {name}')
    changed.append('release-manifest.json')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'archive' / f'{stamp}-before-play-update.zip'
    saved = {name: (play / name).read_bytes() for name in changed if name in before}
    rollback = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'old_executable_sha256': before['MoJin.exe'], 'new_executable_sha256': digest,
                'files': {name: sha(data) for name, data in saved.items()},
                'new_files': [name for name in changed if name not in before],
                'restore': 'With the game closed, restore files under play/ to the project play folder. Keep saves/settings/userdata/logs; newly added fonts may remain.'}
    with zipfile.ZipFile(backup, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in saved.items():
            z.writestr('play/' + name, data)
        z.writestr('rollback.json', json.dumps(rollback, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(backup) as z:
        assert z.testzip() is None
        for name, expected in rollback['files'].items():
            assert sha(z.read('play/' + name)) == expected
        sample = ROOT / 'development/tests/archive-restore' / backup.stem / 'MoJin.exe'
        sample.parent.mkdir(parents=True)
        sample.write_bytes(z.read('play/MoJin.exe'))
        assert sha(sample.read_bytes()) == before['MoJin.exe']
    # Stage every replacement before touching play. Existing hardlinks stay intact.
    stage = ROOT / 'development/releases' / f'promotion-{stamp}'
    for name in changed:
        target = safe_file(stage, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if name.startswith('data/game/'):
            os.link(safe_file(package, name), target)
        else:
            shutil.copy2(safe_file(package, name), target)
        assert sha(target.read_bytes()) == sha((package / name).read_bytes())
    for name in changed:
        target = safe_file(play, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage / name, target)
    after = {p.relative_to(play).as_posix(): sha(p.read_bytes()) for p in play.rglob('*') if p.is_file() and p.name != '.session.lock'}
    for name, expected in before.items():
        if name not in changed:
            assert after[name] == expected, f'Preserved file changed: {name}'
    for name, info in new['files'].items():
        if not mutable(name):
            assert after[name] == info['sha256'], name
    result = dict(version=new['version'], executable_sha256=digest, installed_files=changed,
                  preserved_files=len(before)-sum(name in before for name in changed),
                  preserved_mutable_files={name: value for name, value in before.items() if mutable(name)},
                  rollback_archive=str(backup.relative_to(ROOT)), rollback_sha256=sha(backup.read_bytes()),
                  rollback_crc_and_hashes_verified=True, rollback_disk_sample=str(sample.relative_to(ROOT)),
                  matching_source_archive=str(source_archive.relative_to(ROOT)),
                  source_archive_sha256=sha(source_archive.read_bytes()),
                  source_archive_all_hashes_verified=True,
                  launch_evidence=str(args.launch_evidence), icon_evidence=str(args.icon_evidence))
    (ROOT / 'development/evidence/play-promotion.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
