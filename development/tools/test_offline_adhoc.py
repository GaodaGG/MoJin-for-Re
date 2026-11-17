"""Check local lifecycle against pinned PPSSPP semantics; no host network."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

DEV = Path(__file__).resolve().parents[1]
cc = DEV / "toolchain/msys64/ucrt64/bin/gcc.exe"
out = DEV / "build/offline-adhoc-probe.exe"
env = os.environ.copy()
env["PATH"] = str(cc.parent) + os.pathsep + env["PATH"]
subprocess.run([str(cc), "-O1", "-Werror", "-I" + str(DEV / "third_party/nakagawa/src/rt"),
                str(DEV / "tests/offline_adhoc_probe.c"), "-o", str(out)], env=env, check=True)
run = subprocess.run([str(out)], capture_output=True, text=True, env=env, timeout=10)
expected = ["00000000", "00000000", "80410713", "00000000", "00000000", "00000000", "00000000"]
passed = run.returncode == 0 and run.stdout.splitlines() == expected
result = dict(reference="PPSSPP 4392fe67d06f8a88c317641daa71595f8c540de8 sceNetAdhocInit/NetAdhoc_Term",
              scope="Offline lifecycle only; no PSP hardware or multiplayer validation",
              passed=passed, expected=expected, actual=run.stdout.splitlines(), stderr=run.stderr,
              header_sha256=hashlib.sha256((DEV / "runtime/offline_adhoc.h").read_bytes()).hexdigest())
(DEV / "evidence/offline-adhoc-test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
assert passed, result
print("PASS: 7 offline lifecycle transitions match the pinned reference")
