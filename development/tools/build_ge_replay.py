"""Build the pinned graphics-only fixture tool with this project's rendering overlays."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from build import DEV, ROOT, SRC, REV, local_build_inputs
from prepare_runtime import prepare


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--optimization',choices=['O1','O3'],default='O1')
    args=parser.parse_args()
    prepare()
    if subprocess.check_output(["git", "-C", str(SRC), "rev-parse", "HEAD"], text=True).strip() != REV:
        raise SystemExit("Unvalidated upstream revision")
    if subprocess.check_output(["git", "-C", str(SRC), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise SystemExit("Upstream tracked sources changed")
    out = DEV / ('generated/ge-replay' if args.optimization=='O1' else 'generated/ge-replay-O3')
    out.mkdir(parents=True, exist_ok=True)
    toolroot = DEV / "toolchain/msys64/ucrt64"
    env = os.environ.copy()
    env.update(OS="Windows_NT", PYTHONIOENCODING="utf-8")
    env["PATH"] = str(toolroot / "bin") + os.pathsep + env["PATH"]
    # Use this tool's own object directory. Upstream build-profile bookkeeping can
    # invalidate RT_GE_O even with make -o, so never point it at the game's object.
    ge_object = out / "ge.o"
    inputs = local_build_inputs()
    for path in (DEV / "ge-replay.mk", Path(__file__)):
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    command = [str(toolroot / "bin/mingw32-make.exe"), "-f", (DEV / "ge-replay.mk").as_posix(),
        "ge-replay", "-j1", f"MOJIN_DEV={DEV.as_posix()}", f"BUILD_DIR={out.as_posix()}",
        f"BUILD_ROOT={(DEV / 'build').as_posix()}",
        f"PYTHON={(DEV / 'toolchain/python/python.exe').as_posix()}",
        f"SDL3_DIR={toolroot.as_posix()}", f"VULKAN_SDK={toolroot.as_posix()}",
        f"RUNTIME_OPT=-{args.optimization}", "TRACE=0", "SHELL=cmd.exe"]
    log = DEV / "evidence/build-ge-replay.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=SRC, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(encoding="utf-8", errors="replace")[-10000:])
        raise SystemExit(result.returncode)
    for name, expected in inputs.items():
        if sha(ROOT / name) != expected:
            raise SystemExit(f"Input changed during build: {name}")
    exe = out / "ge_replay.exe"
    record = dict(purpose="Graphics fixture replay only; no game CPU execution", source_revision=REV,
                  command=command, local_inputs=inputs, executable_sha256=sha(exe), ge_object_sha256=sha(ge_object))
    exe.with_suffix(".build.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Built {exe}\nSHA256 {record['executable_sha256']}\nLog {log}")


if __name__ == "__main__":
    main()
