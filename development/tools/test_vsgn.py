"""Compile the actual lowering; check recorded bit patterns, overlap, and fail-closed prefixes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

DEV = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mojin_codegen", DEV / "tools/codegen.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)
out = DEV / "build/vsgn-test"
out.mkdir(parents=True, exist_ok=True)
words = [0xd04a0008, 0xd04a0088, 0xd04a8008, 0xd04a8088, 0xd04a80c0]
text = '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "recomp.h"\n'
# Exercise the actual pinned production prefix helpers, with their notices retained.
runtime = (DEV / "third_party/nakagawa/src/rt/recomp.c").read_text(encoding="utf-8")
start = runtime.index("static const float SR_VFPU_CONST[8]")
end = runtime.index("/* ---- dispatch table", start)
text += "/* GPL-2.0-or-later; Nakagawa/psp-recomp/PPSSPP prefix helpers. */\n" + runtime[start:end]
for i, word in enumerate(words):
    text += f"static void cell{i}(CpuState *s) " + cg.vsgn(0x08804000, word, None, None)[0] + "\n"
text += r'''
static const uint32_t values[] = {0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,
    0x00800000,0x80800000,0x40200000,0xc0600000,0x7f800000,0xff800000,
    0x7fc00000,0xffc00000,0x7f800001,0xff800001};
static const uint32_t expected[] = {0,0,0,0,0,0,0x3f800000,0xbf800000,
    0x3f800000,0xbf800000,0x3f800000,0xbf800000,0x3f800000,0xbf800000,0x3f800000,0xbf800000};
static void (*cells[])(CpuState *) = {cell0,cell1,cell2,cell3,cell4};
int main(int argc, char **argv) {
    CpuState state, want;
    if (argc > 1) {
        memset(&state,0,sizeof state);
        state.vfpuCtrl[0]=state.vfpuCtrl[1]=0xe4;
        state.vfpuCtrl[atoi(argv[1])]^=1;
        cell0(&state);
        return 99;
    }
    unsigned cases=0;
    for (int form=0;form<5;form++) for (int first=0;first<16;first++) {
        memset(&state,0x35,sizeof state);
        state.vfpuCtrl[0]=state.vfpuCtrl[1]=0xe4; state.vfpuCtrl[2]=0;
        for (int i=0;i<4;i++) state.vi[i]=values[(first+i)%16];
        want=state;
        int width=form==4?4:form+1;
        for (int i=0;i<width;i++) want.vi[form==4?(i+2)%4:32+i]=expected[(first+i)%16];
        cells[form](&state);
        if (memcmp(&state,&want,sizeof state)) {
            fprintf(stderr,"mismatch form=%d first=%d\n",form,first); return 1;
        }
        cases++;
    }
    /* The prefix combination observed at game PC 0x08953980: negate lane 1,
       saturate lane 1 to [0,1], mask lanes 2/3. Values themselves are synthetic. */
    memset(&state,0x35,sizeof state);
    state.vi[0]=0x40200000; state.vi[1]=0x40600000;
    state.vfpuCtrl[0]=0x200e4; state.vfpuCtrl[1]=0xe4; state.vfpuCtrl[2]=0xc04;
    want=state; want.vi[32]=0x3f800000; want.vi[33]=0;
    want.vfpuCtrl[0]=want.vfpuCtrl[1]=0xe4; want.vfpuCtrl[2]=0;
    cell1(&state); if(memcmp(&state,&want,sizeof state)) return 3; cases++;
    /* Source swizzle outside scalar width reads zero, including with negation. */
    state=want; state.vfpuCtrl[0]=0x100e5;
    want=state; want.vi[32]=0; want.vfpuCtrl[0]=0xe4;
    cell0(&state); if(memcmp(&state,&want,sizeof state)) return 4; cases++;
    /* D mask leaves the old destination; prefix state is still consumed. */
    state=want; state.vfpuCtrl[2]=0x100;
    want=state; want.vfpuCtrl[2]=0;
    cell0(&state); if(memcmp(&state,&want,sizeof state)) return 5; cases++;
    printf("PASS: %u compiled VSGN cases, full CPU-state comparison\n",cases);
    return 0;
}
'''
assert "sr_vfpu_interp(" not in text
c = out / "test.c"
c.write_text(text, encoding="utf-8", newline="\n")
exe = out / "test.exe"
cc = DEV / "toolchain/msys64/ucrt64/bin/gcc.exe"
env = os.environ.copy()
env["PATH"] = str(cc.parent) + os.pathsep + env["PATH"]
subprocess.run([str(cc), "-O2", "-Werror", "-I" + str(DEV / "third_party/nakagawa/src/rt"),
                str(c), "-o", str(exe)], check=True, env=env)
results = []
for args in ([], ["1"]):
    r = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=10, env=env)
    passed = r.returncode == (87 if args else 0)
    results.append(dict(args=args, exit_code=r.returncode, passed=passed, stdout=r.stdout, stderr=r.stderr))
(DEV / "evidence/vsgn-test.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
assert all(x["passed"] for x in results), results
print(results[0]["stdout"].strip())
print("PASS: unvalidated T prefix is rejected before execution")
