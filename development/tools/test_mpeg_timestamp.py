"""Compile both actual parsers and compare with raw ISO header values, including the lost byte."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from inspect_input import Iso
from prepare_runtime import prepare_mpeg_timestamp

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
prepare_mpeg_timestamp()
work = DEV / "build/mpeg-timestamp-test"
work.mkdir(parents=True, exist_ok=True)
iso = Iso(ROOT / "魔法禁书目录.iso")
cases = []
try:
    for entry in iso.entries:
        if entry["directory"] or not entry["path"].upper().endswith(".PMF"):
            continue
        header = iso.read(entry["offset"], 2048)
        assert header[:4] == b"PSMF"
        for field, offset in (("first", 0x54), ("last", 0x5a)):
            raw = header[offset:offset + 6]
            assert raw[0] == 0  # reserved leading bits aren't a measured firmware contract
            cases.append(dict(name=entry["path"] + ":" + field, raw=raw.hex(),
                              expected=int.from_bytes(raw, "big"), header_sha256=hashlib.sha256(header).hexdigest()))
finally:
    iso.file.close()
for name, raw in (("low-byte-1", "000000000001"), ("low-byte-255", "0000000000ff"),
                  ("multi-byte", "000012345678"), ("above-32-bits", "000100000001"),
                  ("reference-leading-zero-limit", "00ffffffffff"), ("zero", "000000000000")):
    cases.append(dict(name=name, raw=raw, expected=int.from_bytes(bytes.fromhex(raw), "big")))
toolbin = DEV / "toolchain/msys64/ucrt64/bin"
env = os.environ.copy()
env["PATH"] = str(toolbin) + os.pathsep + env.get("PATH", "")
rows = []
for label, source_path in (("before", DEV / "third_party/nakagawa/src/rt/mpeg.c"),
                           ("after", DEV / "generated/runtime/mpeg.c")):
    source = source_path.read_text(encoding="utf-8")
    start = source.index("static int64_t mpeg_ts(")
    function = source[start:source.index("\n}", start) + 2]
    harness = '''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static uint8_t bytes[6];
static unsigned seen;
static uint8_t read_byte(uint32_t a) { if (a >= 6) exit(11); seen |= 1u << a; return bytes[a]; }
#define MEM_R8(a) read_byte(a)
''' + function + '''
int main(int argc, char **argv) {
    if (argc != 2) return 12;
    for (unsigned i=0;i<6;i++) { unsigned v; if (sscanf(argv[1]+2*i,"%2x",&v)!=1) return 13; bytes[i]=(uint8_t)v; }
    long long value = (long long)mpeg_ts(0);
    printf("%lld %u\\n", value, seen);
    return 0;
}
'''
    cfile, exe = work / (label + ".c"), work / (label + ".exe")
    cfile.write_text(harness, encoding="utf-8")
    command = [str(toolbin / "gcc.exe"), "-O2", "-Wall", "-Wextra", "-Werror", str(cfile), "-o", str(exe)]
    subprocess.run(command, env=env, check=True)
    for case in cases:
        result = subprocess.run([str(exe), case["raw"]], capture_output=True, text=True, env=env, check=True)
        value, read_mask = map(int, result.stdout.split())
        rows.append(dict(build=label, **case, actual=value, read_mask=read_mask,
                         value_matches=value == case["expected"], reads_exact_six_bytes=read_mask == 63,
                         source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest()))
ok = all(r["value_matches"] and r["reads_exact_six_bytes"] for r in rows if r["build"] == "after")
ok = ok and all(not r["value_matches"] for r in rows if r["build"] == "before" and r["name"] != "zero")
report = dict(passed=ok, reference="https://github.com/hrydgard/ppsspp/blob/4392fe67d06f8a88c317641daa71595f8c540de8/Core/HW/MediaEngine.h#L40-L42",
              scope="Actual compiled parser; six raw movie header fields plus edge cases with zero leading reserved byte. Does not prove decoded A/V or firmware behavior for other reserved-bit patterns.", cases=rows)
(DEV / "evidence/mpeg-timestamp-test.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"Passed={ok}; {len(cases)} fields/vectors per parser; old parser regression reproduced")
raise SystemExit(0 if ok else 1)
