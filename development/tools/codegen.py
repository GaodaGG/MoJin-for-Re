"""Game-independent Allegrex lowering additions over the pinned generator.

SPDX-License-Identifier: GPL-3.0-or-later
vsgn identity-prefix semantics cross-checked against:
  Nakagawa 2263985 tests/native/vfpu_interp_selftest.c (recorded PSP cases)
  PPSSPP 4392fe67 Core/MIPS/InterpreterVFPU.cpp::Int_Vsgn (GPL-2.0-or-later)
This file does not modify generated game code after generation.
"""
import importlib.util
import hashlib
import os
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1] / "third_party/nakagawa/tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("nakagawa_codegen", TOOLS / "codegen.py")
upstream = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = upstream
spec.loader.exec_module(upstream)

# An observed jump may skip canonical alignment NOPs at an existing callable.
# Prove that relationship before seeding; keep all other upstream entry checks.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from entry_proof import install as install_entry_proof
install_entry_proof(upstream)

# Read-only loop observations are emitted alongside the pinned instructions.
# This is not a frame-rate patch: no guest register, opcode or clock is changed.
LOOP_TRACE_SITES = {
    0x0880a620: 0x24040005,  # before callback phase 5
    0x0880a62c: 0x24040006,  # before callback phase 6
    0x0880a638: 0x24040007,  # before callback phase 7
    0x0880a644: 0x8e42d108,  # after frame-end / vblank wait
    0x08907c44: 0x27bdfff0,  # common update entry, before timing calculations
    0x08907d6c: 0x00000000,  # timing calculated, before title update callback
    0x0891d368: 0x8e231908,  # common update returned to the engine loop
}
loop_trace_seen = set()
stock_normal_line = upstream.normal_line


def observed_normal_line(addr, word, *args, **kwargs):
    line = stock_normal_line(addr, word, *args, **kwargs)
    if addr in LOOP_TRACE_SITES:
        if word != LOOP_TRACE_SITES[addr]:
            raise ValueError(f"Loop observation instruction changed at {addr:08x}")
        loop_trace_seen.add(addr)
        line = ("    { extern void mojin_loop_trace(const CpuState *, uint32_t); "
                f"mojin_loop_trace(s, 0x{addr:08x}u); }}\n" + line)
    return line


upstream.normal_line = observed_normal_line

# Developer-only frame-clock feasibility experiment. Preserve the ordinary
# call, its delay slot and its AOT return-boundary checks as the default path.
stock_emit_jal = upstream._emit_jal
stock_checked_body_call = upstream.emit_checked_body_call
frame_wait_seen = False
input_poll_seen = False
FRAME_CALL_TRACE_SITES = {
    0x0891d318: (0x0e246e1e, 0x82241924),  # next loop prelude
    0x0891d320: (0x0e242633, 0x24040001),  # title input processing
    0x0891d730: (0x0e25bad3, 0x24050001),  # one controller sample
    0x0891d36c: (0x0e241f64, 0xae23190c),  # post-update title callback
    0x0891d374: (0x0e246ef7, 0x00000000),  # command generation
    0x0891d3d8: (0x0e246fc5, 0x00000000),  # common frame end
    0x0891d3e0: (0x0e246f9d, 0x00000000),  # next command-list setup
    0x0891d410: (0x0e246fc5, 0xa2c20008),  # alternate branch, same frame end
    0x0891d418: (0x0e246f9d, 0x00000000),
    0x0891bf54: (0x0e2517bc, 0xae2218c8),  # graphics completion call
    0x0891bf68: (0x0e25badb, 0xae2218d0),  # ordinary / experimental wait
    0x0891bf70: (0x0e25ba85, 0x00000000),  # after wait, read system time
}
frame_trace_seen = set()


def frame_trace_line(pc):
    return ('    { extern void mojin_frame_trace(const CpuState *, uint32_t); '
            f'mojin_frame_trace(s, 0x{pc:08x}u); }}')


def experimental_emit_jal(ctx, out, addr, word, ds, dsw):
    if addr in FRAME_CALL_TRACE_SITES:
        if (word, dsw) != FRAME_CALL_TRACE_SITES[addr] or ds != addr + 4:
            raise ValueError(f'Frame observation call/delay slot changed at {addr:08x}')
        frame_trace_seen.add(addr)
        out.append(frame_trace_line(addr))
    if addr == 0x0891bf68:
        if (word, ds, dsw) != (0x0e25badb, 0x0891bf6c, 0xae2218d0):
            raise ValueError("Common frame-wait instruction/delay slot changed")
    result = stock_emit_jal(ctx, out, addr, word, ds, dsw)
    if addr in (0x0891d3e0, 0x0891d418, 0x0891d730):
        out.append(frame_trace_line(addr + 8))
    return result


def experimental_checked_body_call(symbol, call_pc):
    global frame_wait_seen, input_poll_seen
    line = stock_checked_body_call(symbol, call_pc)
    if call_pc == 0x0891bf68:
        if symbol != "f_0896eb6c":
            raise ValueError("Common frame-wait target changed")
        original = f"{symbol}(s);"
        assert line.count(original) == 1
        replacement = ("{ extern int mojin_experimental_frame_wait(CpuState *); "
                       f"if (!mojin_experimental_frame_wait(s)) {original} }}")
        line = line.replace(original, replacement)
        frame_wait_seen = True
    if call_pc == 0x0891d730:
        if symbol != 'f_0896eb4c':
            raise ValueError('Common controller-read target changed')
        original = f'{symbol}(s);'
        assert line.count(original) == 1
        replacement = ('{ extern int mojin_experimental_input_poll(CpuState *); '
                       f'if (!mojin_experimental_input_poll(s)) {original} }}')
        line = line.replace(original, replacement)
        input_poll_seen = True
    return line


upstream._emit_jal = experimental_emit_jal
upstream.emit_checked_body_call = experimental_checked_body_call


def vsgn(addr, word, options, delay_branch_pc):
    n = upstream.vec_size(word)
    source = upstream.vreg_indices((word >> 8) & 127, n)
    dest = upstream.vreg_indices(word & 127, n)
    # Registers and widths are resolved during generation. Runtime prefix helpers
    # operate on values; they never fetch/decode instructions. Read before write.
    body = ("{ if (s->vfpuCtrl[1]!=0xe4u) { "
            f'fprintf(stderr,"MOJIN_AOT_REQUIRED kind=vsgn-prefix pc=0x{addr:08x} '
            'S=%08x T=%08x D=%08x\\n",s->vfpuCtrl[0],s->vfpuCtrl[1],s->vfpuCtrl[2]); '
            f"exit(87); }} float _mojin_s[4],_mojin_d[4]; "
            f"sr_vread(_mojin_s,s,{upstream._arr(source)},{n},s->vfpuCtrl[0]); ")
    for lane in range(n):
        body += (f"{{ uint32_t _bits; memcpy(&_bits,&_mojin_s[{lane}],4); "
                 f"_mojin_d[{lane}]=(_bits&0x7f800000u)==0u ? 0.0f : "
                 "((_bits&0x80000000u) ? -1.0f : 1.0f); } ")
    body += f"sr_vwrite(s,{upstream._arr(dest)},_mojin_d,{n},s->vfpuCtrl[2]); "
    body += upstream._EAT + " }"
    return body, None, 0


upstream._VFPU4_VOCP_OP9_FORMS[10] = vsgn


def horizontal_sum(addr, word, options, delay_branch_pc):
    """VFAD/VAVG use the precompiled VFPU adder; opcode/registers lower here."""
    n = upstream.vec_size(word)
    if n < 2:
        raise upstream.Unsupported(f"Unvalidated scalar VFAD/VAVG at 0x{addr:08x}")
    average = ((word >> 16) & 31) == 7
    factor = {2: 0x3f000000, 3: 0x3eaaaaab, 4: 0x3e800000}[n] if average else 0x3f800000
    source = upstream.vreg_indices((word >> 8) & 127, n)
    dest = upstream.vreg_indices(word & 127, 1)[0]
    # Match the pinned runtime's supported prefix contract. Keep unmeasured
    # T/D prefixes and S swizzles beyond the vector width fail-closed.
    bad_swizzles = [f"(!((_p >> {12+i}) & 1u) && ((_p >> {2*i}) & 3u) >= {n}u)" for i in range(n)]
    invalid = " || ".join(["s->vfpuCtrl[1]!=0xe4u", "s->vfpuCtrl[2]!=0u", *bad_swizzles])
    body = ("{ uint32_t _p=s->vfpuCtrl[0]; " + f"if ({invalid}) {{ "
            f'fprintf(stderr,"MOJIN_AOT_REQUIRED kind=horizontal-prefix pc=0x{addr:08x} '
            'S=%08x T=%08x D=%08x\\n",_p,s->vfpuCtrl[1],s->vfpuCtrl[2]); exit(87); } '
            "float _values[4]; uint32_t _bits[4]; "
            f"const uint32_t _factors[4]={{{','.join(f'0x{factor:08x}u' for _ in range(4))}}}; "
            f"sr_vread(_values,s,{upstream._arr(source)},{n},_p); "
            f"memcpy(_bits,_values,{n}*sizeof(uint32_t)); "
            f"s->vi[{dest}]=sr_vfpu_dot_bits(_bits,_factors,{n}); " + upstream._EAT + " }")
    return body, None, 0


upstream._VFPU4_VOCP_OP9_FORMS[6] = horizontal_sum
upstream._VFPU4_VOCP_OP9_FORMS[7] = horizontal_sum

def generate(argv):
    global frame_wait_seen, input_poll_seen
    loop_trace_seen.clear()
    frame_trace_seen.clear()
    frame_wait_seen = False
    input_poll_seen = False
    # Preserve timestamps only for byte-identical output, so an emitter fix
    # does not recompile unrelated translated units. No output content is patched.
    positionals = [x for x in argv[1:] if not x.startswith("--")]
    index = 0 if "--env-elf" in argv else 1
    if len(positionals) <= index:
        return upstream.main(argv)
    target = Path(positionals[index])
    previous = {}
    for path in target.parent.glob(target.stem + "*"):
        if path.suffix not in (".c", ".h", ".json", ".txt"):
            continue
        info = path.stat()
        previous[path] = (hashlib.sha256(path.read_bytes()).digest(), info.st_atime_ns, info.st_mtime_ns)
    result = upstream.main(argv)
    if result == 0:
        if loop_trace_seen != set(LOOP_TRACE_SITES):
            raise ValueError(f"Missing loop observation sites: {set(LOOP_TRACE_SITES) - loop_trace_seen}")
        if not frame_wait_seen:
            raise ValueError("Missing common frame-wait experiment site")
        if not input_poll_seen:
            raise ValueError('Missing common controller-read experiment site')
        if frame_trace_seen != set(FRAME_CALL_TRACE_SITES):
            raise ValueError(f'Missing frame call observations: {set(FRAME_CALL_TRACE_SITES) - frame_trace_seen}')
        unchanged = 0
        for path, (digest, atime, mtime) in previous.items():
            if path.exists() and hashlib.sha256(path.read_bytes()).digest() == digest:
                os.utime(path, ns=(atime, mtime))
                unchanged += 1
        print(f"MOJIN_INCREMENTAL preserved_timestamps={unchanged}")
    return result


if __name__ == "__main__":
    sys.exit(generate(sys.argv))
