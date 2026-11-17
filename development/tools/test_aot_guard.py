import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
cc = DEV / "toolchain/msys64/ucrt64/bin/gcc.exe"
out = DEV / "build/aot-guard-probe.exe"
env = os.environ.copy()
env["PATH"] = str(cc.parent) + os.pathsep + env["PATH"]
subprocess.run([str(cc), "-O1", "-Werror", "-DMOJIN_GUEST_GUARD", "-DMOJIN_VFPU_GUARD",
                "-I" + str(DEV / "third_party/nakagawa/src/rt"),
                str(DEV / "runtime/aot_guard.c"), str(DEV / "tests/aot_guard_probe.c"),
                "-o", str(out)], env=env, check=True)
results = []
for index, kind in enumerate(["dispatch", "tail", "call", "vfpu-needs-static-lowering"]):
    run = subprocess.run([str(out), str(index)], capture_output=True, text=True, env=env, timeout=10)
    passed = run.returncode == 86 and f"kind={kind} " in run.stderr and "pc=0x08804114" in run.stderr
    results.append(dict(kind=kind, exit_code=run.returncode, passed=passed, stderr=run.stderr))
(DEV / "evidence/aot-guard-test.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
assert all(x["passed"] for x in results), results
print("PASS: all four CPU interpretation entry points terminate with an address and exit 86")
