"""Build the diagnostic port from the pinned input and source. No emulator frontend."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

# The pinned embeddable Python omits the script directory from its fixed ._pth.
# Resolve this project's sibling build modules without changing shared Python.
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
SRC = DEV / "third_party/nakagawa"
REV = "2263985dd8882acbbf1a7313f3752979e7f88e2d"
ISO_SHA = "40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb"


def local_build_inputs():
    paths = [DEV / "mojin.mk", DEV / "inputs/dispatch-seeds.txt"]
    paths += [DEV / "tools" / name for name in ("build.py", "codegen.py", "entry_proof.py", "prepare_runtime.py", "pipeline_catalog.py", "disc_data.py", "upstream_source.py", "prepared_game.py")]
    paths += [p for p in (DEV / "runtime").iterdir() if p.suffix in (".c", ".h")]
    paths += [p for p in (DEV / "assets").rglob("*") if p.is_file()]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["pipeline", "compile", "all", "prepared"], default="all", nargs="?")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output-name", default="mojin.exe", help="Executable filename in generated/baseline; enables isolated candidates")
    args = parser.parse_args()
    if not re.fullmatch(r"mojin(?:-[A-Za-z0-9_-]+)?\.exe", args.output_name):
        parser.error("--output-name must be a mojin*.exe filename without a path")
    from upstream_source import verify as verify_upstream
    upstream = verify_upstream()
    from prepare_runtime import prepare
    prepare()
    from disc_data import prepare as prepare_disc
    prepare_disc()
    source_hashes = local_build_inputs()
    rev = upstream['revision']
    if rev != REV:
        raise SystemExit(f"Unvalidated source revision {rev}; expected {REV}")
    prepared = args.action == 'prepared'
    if prepared:
        from prepared_game import stage
        provenance = stage()
        from disc_data import verify as verify_resources
        verify_resources()
    else:
        iso = ROOT / "魔法禁书目录.iso"
        with iso.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if digest != ISO_SHA:
            raise SystemExit("Input changed: refusing version-specific build")
        from inspect_input import Iso
        image = Iso(iso)
        elf = image.get("/PSP_GAME/SYSDIR/EBOOT.BIN")
        image.file.close()
        input_dir = DEV / "inputs"
        input_dir.mkdir(exist_ok=True)
        elf_path = input_dir / "EBOOT.elf"
        if not elf_path.exists() or elf_path.read_bytes() != elf:
            if elf_path.exists():
                raise SystemExit("Extracted executable differs; preserve it and investigate")
            elf_path.write_bytes(elf)
        provenance = dict(mode='raw-iso', iso_opened=True, elf_opened=True)
    toolroot = DEV / "toolchain/msys64/ucrt64"
    py = DEV / "toolchain/python/python.exe"
    make = toolroot / "bin/mingw32-make.exe"
    env = os.environ.copy()
    # Use one shared portable toolchain. Do not change the machine's PATH.
    env["PATH"] = os.pathsep.join((str(toolroot / "bin"), str(py.parent), env["PATH"]))
    env["PYTHONIOENCODING"] = "utf-8"
    env["OS"] = "Windows_NT"
    for key in list(env):
        if key.startswith('GAME_'):
            env.pop(key)
    if not prepared:
        env["GAME_ELF"] = elf_path.as_posix()
    # Upstream declares C/header as independent make targets sharing one writer.
    # Finish generation serially before allowing parallel compilation, including
    # for "compile" requests, so updated instruction semantics cannot be skipped.
    commands = ['compile'] if prepared else (["pipeline"] if args.action == "pipeline" else ["pipeline", "compile"])
    common = [str(make), "-f", (DEV / "mojin.mk").as_posix(),
              "GAME_NAME=mojin", "GAME_BASE=0x08804000", "GAME_ENTRY=0x08804114",
              f"MOJIN_DEV={DEV.as_posix()}", f"PYTHON={py.as_posix()}",
              f"CODEGEN_TOOL={(DEV / 'tools/codegen.py').as_posix()}",
              f"CODEGEN_USER_ARGS=--miss-seeds={(DEV / 'inputs/dispatch-seeds.txt').as_posix()}",
              f"BUILD_ROOT={(DEV / 'build').as_posix()}",
              f"BUILD_DIR={(DEV / 'generated/baseline').as_posix()}",
              f"TITLE_OUTPUT={(DEV / 'generated/baseline' / args.output_name).as_posix()}",
              f"SDL3_DIR={toolroot.as_posix()}", f"VULKAN_SDK={toolroot.as_posix()}",
              "FUNCS_PER_CHUNK=64",
              "RUNTIME_OPT=-O1", "RECOMP_OPT=-O1", "TRACE=0", "SHELL=cmd.exe"]
    if prepared:
        common += ['GAME_INPUT_TRACKED=', 'NK_AOT_PREGENERATED=1']
    for command in commands:
        log = DEV / f"evidence/build-{command}.log"
        argv = common + [command, f"-j{1 if command == 'pipeline' else args.jobs}"]
        if command == "compile":
            argv.append("NK_AOT_PREGENERATED=1")
        (DEV / f"evidence/build-{command}-command.json").write_text(json.dumps(argv, indent=2), encoding="utf-8")
        print(f"Running {command}; log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as out:
            result = subprocess.run(argv, cwd=SRC, env=env, stdout=out, stderr=subprocess.STDOUT)
        print(f"{command}: exit {result.returncode}", flush=True)
        print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]))
        if result.returncode:
            return result.returncode
    if "compile" in commands:
        if prepared:
            from prepared_game import verify_staged
            verify_staged(provenance)
        if source_hashes != local_build_inputs():
            raise SystemExit("Build inputs changed during compilation; candidate is not certified")
        exe = DEV / "generated/baseline" / args.output_name
        manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), source_revision=REV,
                        source_verification={k:v for k,v in upstream.items() if k!='files'},
                        game_input=provenance,
                        input_iso_sha256=ISO_SHA, local_build_inputs=source_hashes,
                        executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                        image_sha256=hashlib.sha256(exe.with_name("mojin_image.bin").read_bytes()).hexdigest())
        exe.with_suffix(".build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
