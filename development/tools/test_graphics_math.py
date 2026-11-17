"""Compare production graphics min/max wrappers with the pinned C runtime, bit for bit."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'development'
def main():
    out=DEV/'tests/graphics-math'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    gcc=DEV/'toolchain/msys64/ucrt64/bin/gcc.exe'
    source=DEV/'tests/graphics_math_test.c'
    exe=out/'check.exe'
    env=dict(os.environ,PATH=str(gcc.parent)+os.pathsep+os.environ['PATH'])
    command=[str(gcc),'-O3','-Wall','-Wextra','-Werror','-I'+str(DEV/'runtime'),str(source),'-o',str(exe)]
    subprocess.run(command,env=env,check=True)
    result=subprocess.run([str(exe)],env=env,capture_output=True,text=True)
    (out/'stdout.log').write_text(result.stdout)
    (out/'stderr.log').write_text(result.stderr)
    if result.returncode:
        raise SystemExit(result.stderr)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record=dict(passed=True,output=result.stdout.strip(),command=command,
        header_sha256=sha(DEV/'runtime/graphics_math.h'),test_sha256=sha(source),executable_sha256=sha(exe),
        limits=['Pinned GCC/Windows runtime, result bits only; actual frame comparison is separate.'])
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    (DEV/'evidence/graphics-math-test.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
