"""Archive project sources and a tested diagnostic binary, then verify restore.

No input ISO, extracted ELF, toolchain or third-party source is duplicated here.
The manifest points to the one shared copy and pinned recovery sources instead.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="Existing completed test run under development/tests/runs")
    parser.add_argument("--replay", type=Path, help="Matching private graphics replay evidence to preserve")
    parser.add_argument("--graphics-comparison", type=Path, help="Verified pipeline-preparation equivalence fixture and exact graphics executable")
    parser.add_argument("--standalone-package", type=Path, help="Verified private package manifest and mutable launch evidence; static dependencies remain shared")
    parser.add_argument("--settings-ui", type=Path, help="Completed private overlay/persistence test to preserve")
    parser.add_argument("--extra-run", type=Path, action="append", default=[], help="Additional completed evidence, with its frozen EXE and build record")
    parser.add_argument("--restart", type=Path, help="Verified private no-argument settings restart, excluding shared static dependency links")
    args = parser.parse_args()
    run = Path(args.run).resolve()
    if not run.is_relative_to((DEV / "tests/runs").resolve()) or not (run / "run.json").is_file():
        parser.error("run must name an existing completed project probe")
    manifest = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if "exit_code" not in manifest:
        parser.error("The probe is still running")
    exe = Path(manifest["command"][0]).resolve()
    if not exe.is_relative_to((DEV / "generated").resolve()):
        raise SystemExit("Probe executable is not under the project's generated directory")
    if sha(exe.read_bytes()) != manifest["executable_sha256"]:
        raise SystemExit("Current executable differs from this run; preserve the evidence and choose the matching binary")
    build_path = exe.with_suffix(".build.json")
    if build_path.is_file():
        build_record = json.loads(build_path.read_text(encoding="utf-8"))
        if build_record["executable_sha256"] != manifest["executable_sha256"]:
            raise SystemExit("Build provenance does not match the tested executable")
        for name, digest in build_record["local_build_inputs"].items():
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT) or sha(source.read_bytes()) != digest:
                raise SystemExit(f"Build source changed since this executable was compiled: {name}")
    paths = [ROOT / "README.md", ROOT / "CONTINUE.md", ROOT / ".gitignore",
             DEV / "DEVELOPMENT.md", DEV / "mojin.mk", DEV / "Start-Visible-Battle.cmd", exe]
    paths.extend(DEV.glob("*.mk"))
    if exe.with_suffix(".build.json").is_file():
        paths.append(exe.with_suffix(".build.json"))
        # Every pinned local build input is required for this exact candidate,
        # including resource scripts/icons and future non-code build assets.
        paths.extend(ROOT / name for name in build_record["local_build_inputs"])
    for directory, suffixes in [(DEV / "tools", {".py"}), (DEV / "runtime", {".c", ".h"}),
                                 (DEV / "tests", {".c", ".pad"}), (DEV / "inputs", {".txt"})]:
        paths.extend(p for p in directory.iterdir() if p.is_file() and p.suffix in suffixes)
    paths.extend(p for p in (DEV / "evidence").iterdir() if p.is_file() and
                 (p.name.startswith("build-") or p.name.endswith("-test.json") or p.name in
                  {"input-inventory.json", "movie-headers.json", "static-vfpu-boundaries.json", "timing-map.json"})
                 and p.stat().st_size < 1024*1024)
    # This run's settings, private saves and diagnostics are required evidence.
    paths.extend(p for p in run.rglob("*") if p.is_file())
    if args.replay:
        replay = args.replay.resolve()
        if not replay.is_relative_to(DEV / "tests/graphics-replay") or not (replay / "result.json").is_file():
            parser.error("replay must name completed project-private graphics evidence")
        replay_record = json.loads((replay / "result.json").read_text(encoding="utf-8"))
        if sha((run / "frame.ngef").read_bytes()) != replay_record["fixture_sha256"]:
            raise SystemExit("Replay fixture differs from the archived run")
        replay_exe = DEV / "generated/ge-replay/ge_replay.exe"
        if sha(replay_exe.read_bytes()) != replay_record["build"]["executable_sha256"]:
            raise SystemExit("Replay executable differs from the archived evidence")
        paths.extend([replay_exe, replay_exe.with_suffix(".build.json")])
        paths.extend(p for p in replay.rglob("*") if p.is_file())
    if args.settings_ui:
        ui = args.settings_ui.resolve()
        if not ui.is_relative_to(DEV / "tests/settings-ui") or not (ui / "result.json").is_file():
            parser.error("settings-ui must name a completed private overlay test")
        ui_record = json.loads((ui / "result.json").read_text(encoding="utf-8"))
        if sha((ui / "settings-test.exe").read_bytes()) != ui_record["executable_sha256"]:
            raise SystemExit("Settings test executable changed")
        for name, digest in ui_record["sources"].items():
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT) or sha(source.read_bytes()) != digest:
                raise SystemExit(f"Settings test source changed: {name}")
        paths.extend(p for p in ui.rglob("*") if p.is_file())
    if args.graphics_comparison:
        comparison=args.graphics_comparison.resolve()
        if not comparison.is_relative_to(DEV/'tests/graphics-replay'):
            parser.error('graphics-comparison must be private project evidence')
        checked=json.loads((comparison/'result.json').read_text(encoding='utf-8'))
        if checked.get('all_passed') is not True:
            raise SystemExit('Graphics comparison did not complete')
        fixture=(ROOT/checked['fixture']).resolve()
        graphics=DEV/'generated/ge-replay/ge_replay.exe'
        if not fixture.is_relative_to(DEV/'tests/runs') or sha(fixture.read_bytes())!=checked['fixture_sha256']:
            raise SystemExit('Graphics comparison fixture changed')
        if sha(graphics.read_bytes())!=checked['build']['executable_sha256']:
            raise SystemExit('Graphics comparison executable changed')
        for row in checked['cases']:
            frame=(comparison/row['case']/'frame.ppm').resolve()
            if not frame.is_relative_to(comparison) or sha(frame.read_bytes())!=row['output_sha256']:
                raise SystemExit('Graphics comparison output changed')
        paths.extend([fixture,graphics,graphics.with_suffix('.build.json')])
        paths.extend(p for p in comparison.rglob('*') if p.is_file())
    for item in args.extra_run:
        extra=item.resolve()
        if not extra.is_relative_to(DEV/'tests/runs'):
            parser.error('extra-run must be a private project probe')
        extra_record=json.loads((extra/'run.json').read_text(encoding='utf-8'))
        if 'exit_code' not in extra_record: parser.error('extra-run is not completed')
        extra_exe=Path(extra_record['command'][0]).resolve()
        if not any(extra_exe.is_relative_to(DEV/p) for p in ('generated','releases','tests/standalone')) or sha(extra_exe.read_bytes())!=extra_record['executable_sha256']:
            raise SystemExit('Extra evidence executable changed')
        paths.append(extra_exe)
        paths.append(extra_exe.with_suffix('.build.json') if extra_exe.with_suffix('.build.json').exists() else extra/'build.json')
        paths.extend(p for p in extra.rglob('*') if p.is_file())
    if args.restart:
        restart=args.restart.resolve()
        if not restart.is_relative_to(DEV/'tests/standalone'):
            parser.error('restart must be a private staged test')
        checked=json.loads((restart/'settings-restart-verification.json').read_text(encoding='utf-8'))
        staged=json.loads((restart/'stage-manifest.json').read_text(encoding='utf-8'))
        if not checked['normal_exit'] or sha((restart/'MoJin.exe').read_bytes())!=checked['executable_sha256']:
            raise SystemExit('Restart evidence changed')
        shared=set(staged['shared_immutable_files'])
        paths.extend(p for p in restart.rglob('*') if p.is_file() and p.relative_to(restart).as_posix() not in shared)
    if args.standalone_package:
        package=args.standalone_package.resolve()
        if not any(package.is_relative_to(DEV/p) for p in ('releases','tests/standalone')):
            parser.error('standalone-package must be a private development release or relocated test')
        launched=json.loads((package/'standalone-test.json').read_text(encoding='utf-8'))
        packaged=json.loads((package/'release-manifest.json').read_text(encoding='utf-8'))
        if launched['exit_code']!=0 or launched['executable_sha256']!=manifest['executable_sha256']:
            raise SystemExit('Standalone test does not match the main candidate')
        for name,row in packaged['files'].items():
            path=(package/name).resolve()
            if not path.is_relative_to(package) or sha(path.read_bytes())!=row['sha256']:
                raise SystemExit('Standalone package changed')
        shared=set(packaged['files'])-{'settings.ini'}
        paths.extend(p for p in package.rglob('*') if p.is_file() and p.relative_to(package).as_posix() not in shared)
    paths = sorted(set(paths))
    entries = {p.relative_to(ROOT).as_posix(): dict(sha256=sha(p.read_bytes()), bytes=p.stat().st_size) for p in paths}
    checkpoint = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        kind="Diagnostic checkpoint; not a playable standalone distribution",
        source_revision=subprocess.check_output(["git", "-C", str(DEV / "third_party/nakagawa"), "rev-parse", "HEAD"], text=True).strip(),
        input_iso_sha256="40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb",
        toolchain_zip_sha256="af52764c7f25d55759cc05545aeb7bc7a6ca1f51aa223dc4ddb47d7bff760a0d",
        tested_run=run.relative_to(ROOT).as_posix(), files=entries)
    archive = ROOT / "archive" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-diagnostic.zip")
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in paths:
            output.write(path, path.relative_to(ROOT).as_posix())
        output.writestr("manifest.json", json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n")
    with zipfile.ZipFile(archive) as restored:
        assert restored.testzip() is None
        for name, row in entries.items():
            data = restored.read(name)
            assert len(data) == row["bytes"] and sha(data) == row["sha256"], name
        # A real on-disk restore sample, kept as verification evidence.
        sample_name = "development/tools/codegen.py"
        sample = DEV / "tests/archive-restore" / archive.stem / "codegen.py"
        sample.parent.mkdir(parents=True)
        sample.write_bytes(restored.read(sample_name))
        assert sha(sample.read_bytes()) == entries[sample_name]["sha256"]
    result = dict(archive=str(archive), archive_sha256=sha(archive.read_bytes()), files_verified=len(entries),
                  crc_passed=True, all_restored_byte_hashes_match=True, disk_restore_sample=str(sample))
    (DEV / "evidence/checkpoint-latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
