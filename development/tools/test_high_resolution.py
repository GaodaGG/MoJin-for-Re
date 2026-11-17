"""Exercise the pinned glyph fidelity tests at every scale through 8, including
the original rejection cells and the new boundary. This does not prove GPU or
whole-game rendering; those require separate Vulkan runs.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from prepare_runtime import prepare_high_resolution

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"
prepare_high_resolution()
work = DEV / "build/glyph-scale8"
work.mkdir(parents=True, exist_ok=True)
upstream = DEV / "third_party/nakagawa/src/rt/gpu_sdl3vk"
source = (upstream / "glyph_recon_selftest.c").read_text(encoding="utf-8")
assert hashlib.sha256(source.encode()).hexdigest() == "b3cf61f44eaee50ae9d6ded1c9e86d99fb5e7768eb4f839d1e0711991dcbd5e4"
test = work / "glyph_recon_selftest.c"
# The upstream harness hardcodes six in its output arrays while its loops use
# NK_GLYPH_MAX_FACTOR. Extend only those capacities, never expected results.
for old, count in {"CELL_W * 6 * CELL_H * 6": 5, "32 * 6 * 8 * 6": 2,
                   "64 * 6 * 8 * 6": 1, "32 * 6 * 32 * 6": 2}.items():
    assert source.count(old) == count, old
    source = source.replace(old, old.replace("* 6", "* NK_GLYPH_MAX_FACTOR"))
test.write_text(source.replace('#include "glyph_recon.h"', '#include "../../generated/runtime/glyph_recon.h"'), encoding="utf-8")
toolbin = DEV / "toolchain/msys64/ucrt64/bin"
env = os.environ.copy()
env["PATH"] = str(toolbin) + os.pathsep + env["PATH"]
exe = work / "glyph_recon_selftest.exe"
command = [str(toolbin / "gcc.exe"), "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(exe),
           str(test), str(DEV / "generated/runtime/glyph_recon.c"), "-lm"]
subprocess.run(command, env=env, check=True)
result = subprocess.run([str(exe)], env=env, text=True, capture_output=True)
record = dict(command=command, max_factor=8, exit_code=result.returncode,
              executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              stdout=result.stdout, stderr=result.stderr,
              scope="Synthetic glyph coverage/colour/shape/edge/isolation/refusal checks at factors 2..8; not GPU/game acceptance")
(DEV / "evidence/high-resolution-glyph-test.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(result.stdout, end="")
print(result.stderr, end="")
raise SystemExit(result.returncode)
