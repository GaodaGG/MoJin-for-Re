"""Show the pinned capture bug, then verify streamed reads and fail-closed limits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from prepare_runtime import prepare_ge_capture
ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
prepare_ge_capture()
work = DEV / "build/ge-capture-streamed"
work.mkdir(parents=True, exist_ok=True)
rt = DEV / "third_party/nakagawa/src/rt"
toolbin = DEV / "toolchain/msys64/ucrt64/bin"
env = os.environ.copy()
env["PATH"] = str(toolbin) + os.pathsep + env["PATH"]
rows = []
for label, source in [("pinned", rt / "ge_capture.c"), ("candidate", DEV / "generated/runtime/ge_capture.c")]:
    exe = work / (label + ".exe")
    command = [str(toolbin / "gcc.exe"), "-O2", "-Wall", "-Wextra", "-Werror", "-I" + str(rt),
               str(DEV / "tests/ge_capture_streamed.c"), str(source), "-o", str(exe)]
    subprocess.run(command, env=env, check=True)
    for mode in ("streamed", "mutation"):
        result = subprocess.run([str(exe), mode, str(work / f"{label}-{mode}.ngef")], env=env, capture_output=True, text=True)
        rows.append(dict(build=label, mode=mode, command=list(command), exit_code=result.returncode,
                         source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         stdout=result.stdout, stderr=result.stderr))
        print(f"{label}/{mode}: exit {result.returncode}; {result.stdout}{result.stderr}", end="")
    if label == "candidate":
        # Preserve the existing fixture format and upstream roundtrip behavior.
        roundtrip = work / "upstream-roundtrip.exe"
        command[command.index(str(DEV / "tests/ge_capture_streamed.c"))] = str(DEV / "third_party/nakagawa/tests/native/ge_capture_selftest.c")
        command[-1] = str(roundtrip)
        subprocess.run(command, env=env, check=True)
        result = subprocess.run([str(roundtrip), str(work / "upstream-roundtrip.ngef")], env=env, capture_output=True, text=True)
        rows.append(dict(build=label, mode="upstream-roundtrip", exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        print(result.stdout, end="")
ok = all(row["exit_code"] == (1 if row["build"] == "pinned" else 0) for row in rows)
(DEV / "evidence/ge-capture-streamed-test.json").write_text(json.dumps(dict(passed=ok, cases=rows,
    boundary="Synthetic memory-order proof only; GPU/CPU-produced RAM rewrites may be conservatively refused. VRAM temporal writes and resumed GE stack are not modeled."), indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if ok else 1)
