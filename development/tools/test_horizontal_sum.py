"""Compile emitted VFAD/VAVG against the pinned PSP-result table, not an interpreter."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

DEV = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mojin_codegen", DEV / "tools/codegen.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)
out = DEV / "build/horizontal-sum-test"
out.mkdir(parents=True, exist_ok=True)
runtime = (DEV / "third_party/nakagawa/src/rt/recomp.c").read_text(encoding="utf-8")
oracle = (DEV / "third_party/nakagawa/tests/native/vfpu_interp_selftest.c").read_text(encoding="utf-8")
header = '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "recomp.h"\n'
text = header + "/* GPL-compatible production arithmetic and upstream recorded PSP vectors. */\n"
text += runtime[runtime.index("static const float SR_VFPU_CONST[8]"):runtime.index("/* ---- dispatch table")]
start = runtime.index("uint32_t sr_vfpu_dot_bits(")
end = runtime.index("\n}", start) + 2
text += runtime[start:end] + "\n"
start = oracle.index("static int check_psp_measured_funnel(void)")
table_start = oracle.index("    static const uint32_t ops[26][4]", start)
table_end = oracle.index("    static const char *const forms", table_start)
text += oracle[table_start:table_end]
words = [0xd0460088, 0xd0468008, 0xd0468088, 0xd0470088, 0xd0478008, 0xd0478088,
         0xd046a588, 0xd0468080]
for i, word in enumerate(words):
    text += f"static void cell{i}(CpuState *s) " + cg.horizontal_sum(0x10000, word, None, None)[0] + "\n"
text += r'''
static void (*cells[])(CpuState *)={cell0,cell1,cell2,cell3,cell4,cell5,cell6,cell7};
int main(int argc, char **argv) {
    CpuState s, expected;
    if(argc>1) {
        memset(&s,0,sizeof s); s.vfpuCtrl[0]=s.vfpuCtrl[1]=0xe4;
        int kind=atoi(argv[1]);
        if(kind==1) s.vfpuCtrl[1]=0;
        if(kind==2) s.vfpuCtrl[2]=1;
        if(kind==3) s.vfpuCtrl[0]=0xe7;
        cell0(&s); return 99;
    }
    unsigned count=0;
    for(int f=0;f<2;f++) for(int z=0;z<3;z++) for(int p=0;p<3;p++) {
        if(p==2 && z<2) continue; // Unvalidated swizzle is tested separately as a refusal.
        for(int i=0;i<26;i++) {
            memset(&s,0x35,sizeof s);
            for(int l=0;l<4;l++) s.vi[l]=ops[i][l];
            s.vfpuCtrl[0]=prefixes[p]; s.vfpuCtrl[1]=0xe4; s.vfpuCtrl[2]=0; s.vfpuCtrl[3]=0x15;
            expected=s; expected.vi[32]=want[f][z][p][i]; expected.vfpuCtrl[0]=0xe4;
            cells[f*3+z](&s);
            if(memcmp(&s,&expected,sizeof s)) {
                fprintf(stderr,"mismatch f=%d z=%d p=%d set=%d got=%08x want=%08x\n",
                        f,z,p,i,s.vi[32],expected.vi[32]); return 1;
            }
            count++;
        }
    }
    // Actual observed register layout/S prefix: 1 - 2 + 3 - 4 = -2.
    memset(&s,0x35,sizeof s);
    s.vi[17]=0x3f800000; s.vi[21]=0x40000000; s.vi[25]=0x40400000; s.vi[29]=0x40800000;
    s.vfpuCtrl[0]=0xa00e4; s.vfpuCtrl[1]=0xe4; s.vfpuCtrl[2]=0;
    expected=s; expected.vi[32]=0xc0000000; expected.vfpuCtrl[0]=0xe4;
    cell6(&s); if(memcmp(&s,&expected,sizeof s)) return 2; count++;
    // Destination overlaps source. Read all lanes before the single write.
    memset(&s,0,sizeof s); s.vfpuCtrl[0]=s.vfpuCtrl[1]=0xe4;
    s.vi[0]=0x3f800000; s.vi[1]=0x40000000; s.vi[2]=0x40400000; s.vi[3]=0x40800000;
    expected=s; expected.vi[0]=0x41200000;
    cell7(&s); if(memcmp(&s,&expected,sizeof s)) return 3; count++;
    // Shared S read-stage constant/abs support; not claimed measured by this project.
    s=expected; s.vfpuCtrl[0]=0x001e4; s.vi[0]=0xc0000000; s.vi[1]=0x3f800000; s.vi[2]=s.vi[3]=0;
    expected=s; expected.vi[32]=0x40400000; expected.vfpuCtrl[0]=0xe4;
    cell2(&s); if(memcmp(&s,&expected,sizeof s)) return 4; count++;
    printf("PASS: %u static VFAD/VAVG cases, complete CPU-state comparisons\n",count);
    return 0;
}
'''
assert "sr_vfpu_interp(" not in text
c = out / "test.c"
c.write_text(text, encoding="utf-8", newline="\n")
cc = DEV / "toolchain/msys64/ucrt64/bin/gcc.exe"
exe = out / "test.exe"
env = os.environ.copy()
env["PATH"] = str(cc.parent) + os.pathsep + env["PATH"]
subprocess.run([str(cc), "-O2", "-Werror", "-I" + str(DEV / "third_party/nakagawa/src/rt"),
                str(c), "-o", str(exe)], check=True, env=env)
results = []
for args in ([], ["1"], ["2"], ["3"]):
    r = subprocess.run([str(exe), *args], capture_output=True, text=True, env=env, timeout=10)
    results.append(dict(args=args, exit_code=r.returncode, passed=r.returncode==(87 if args else 0),
                        stdout=r.stdout, stderr=r.stderr))
(DEV / "evidence/horizontal-sum-test.json").write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8")
assert all(r["passed"] for r in results), results
print(results[0]["stdout"].strip())
print("PASS: unvalidated T/D prefixes and outside-width S swizzle are refused")
