"""Archive a verified release with its local build inputs; verify every restored byte."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    assert package.is_relative_to(ROOT)
    manifest = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not re.fullmatch(r"[0-9A-Za-z.-]+", version):
        raise SystemExit("Invalid package version")
    entries = {}
    shared_resources = {}
    for name, info in manifest["files"].items():
        path = (package / name).resolve()
        assert path.is_relative_to(package)
        data = path.read_bytes()
        assert sha(data) == info["sha256"], name
        if name.startswith('data/game/'):
            shared_resources[name] = info
            continue
        entries["play/" + name] = data
    entries["play/release-manifest.json"] = (package / "release-manifest.json").read_bytes()
    entries['shared-resources.json'] = (json.dumps(dict(files=shared_resources,
        restore='Run python development/tools/disc_data.py extract from the pinned original ISO, then python development/tools/restore_shared_resources.py <restored-runtime-folder>. Existing files are verified and never overwritten.'),indent=2)+'\n').encode()
    for name, expected in manifest["build"]["local_build_inputs"].items():
        data = (ROOT / name).read_bytes()
        assert sha(data) == expected, name
        entries[name] = data
    for name in ["README.md", "LICENSE", "COPYRIGHT.md", "AI_DISCLOSURE.md",
                 "docs/DEVELOPMENT.md", "docs/VALIDATION.md", "docs/CONTINUE.md", "docs/DEPENDENCIES.md",
                 "CONTINUE.md", "development/DEVELOPMENT.md"]:
        if (ROOT / name).is_file():
            entries[name] = (ROOT / name).read_bytes()
    if manifest['build'].get('game_input', {}).get('mode') == 'prepared-c':
        from prepared_game import verify
        prepared = verify()
        for name in [*prepared['files'], 'manifest.json']:
            relative = 'development/prepared/game/' + name
            entries[relative] = (ROOT / relative).read_bytes()
    for path in (ROOT / "development/tools").glob("*.py"):
        entries[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for path in (ROOT / "development/evidence").glob("*test.json"):
        if path.stat().st_size < 1024 * 1024:
            entries[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    inventory = {name: {"sha256": sha(data), "bytes": len(data)} for name, data in entries.items()}
    archive = ROOT / "archive" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-preview-{version}.zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in entries.items():
            z.writestr(name, data)
        z.writestr("restore-manifest.json", json.dumps(inventory, indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, info in inventory.items():
            assert sha(z.read(name)) == info["sha256"], name
        sample = ROOT / "development/tests/archive-restore" / archive.stem
        sample.mkdir(parents=True)
        for name in ["play/MoJin.exe", "development/runtime/standalone.h"]:
            target = sample / Path(name).name
            target.write_bytes(z.read(name))
            assert sha(target.read_bytes()) == inventory[name]["sha256"]
    result = dict(archive=str(archive), sha256=sha(archive.read_bytes()),
                  entries_verified=len(inventory), crc_passed=True,
                  all_restored_hashes_match=True, disk_restore_samples=str(sample),
                  shared_resource_files=len(shared_resources),
                  excludes="Original ISO, loose game resource payloads and shared toolchain; shared-resources.json records exact hashes and restoration commands")
    (ROOT / "development/evidence/preview-archive.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
