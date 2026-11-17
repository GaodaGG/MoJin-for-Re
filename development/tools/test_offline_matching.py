"""Matching pool lifetime checks; not multiplayer or PSP timing acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

DEV = Path(__file__).resolve().parents[1]
cc = DEV / "toolchain/msys64/ucrt64/bin/gcc.exe"
out = DEV / "build/offline-matching-probe.exe"
env = os.environ.copy()
env["PATH"] = str(cc.parent) + os.pathsep + env["PATH"]
subprocess.run([str(cc), "-O1", "-Werror", "-I" + str(DEV / "third_party/nakagawa/src/rt"),
                str(DEV / "tests/offline_matching_probe.c"), "-o", str(out)], env=env, check=True)
run = subprocess.run([str(out)], capture_output=True, text=True, env=env, timeout=10)
result = dict(reference="https://github.com/hrydgard/pspautotests/blob/70e72391/tests/net/adhoc/matching.expected",
              reference_blob="7c6dd5e189e611a7ce962087bbfb059aaa7e829a",
              scope="No contexts or transport; mocked partition checks ownership, not memory mapper/timing",
              passed=run.returncode == 0, stdout=run.stdout, stderr=run.stderr,
              header_sha256=hashlib.sha256((DEV / "runtime/offline_matching.h").read_bytes()).hexdigest())
(DEV / "evidence/offline-matching-test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
assert result["passed"], result
print(run.stdout.strip())
