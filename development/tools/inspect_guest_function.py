"""Read-only index of generated AOT functions and direct references, with compact statements."""
import argparse
from pathlib import Path
import re

DEV = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("address", help="Hex function entry")
parser.add_argument("--limit", type=int, default=100)
parser.add_argument("--offset", type=int, default=0)
parser.add_argument("--calls-only", action="store_true", help="Syntactic call sites only; branch conditions are deliberately not summarized")
args = parser.parse_args()
target = f"{int(args.address, 16):08x}"
functions = []
for path in (DEV / "generated/baseline").glob("mojin_recomp_*.c"):
    source = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"^void f_([0-9a-f]{8})\(CpuState \*s\)", source, re.M))
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(source)
        functions.append((match[1], path, source.count("\n", 0, match.start()) + 1, source[match.start():end]))
for name, path, line, body in functions:
    if name == target:
        print(f"FUNCTION {name} {path.relative_to(DEV)}:{line}")
        compact = []
        for raw in body.splitlines():
            if any(x in raw for x in ("uint32_t _sp_entry", "SR_HOST_STACK_CHECK", "SR_AOT_RETURN_CAPTURE")):
                continue
            raw = raw.replace("s->r[29] = _sp_entry;", "")
            raw = re.sub(r"sr_begin\(s, (0x[0-9a-f]+)u, 0x[0-9a-f]+u\);", r"/*\1*/", raw)
            raw = re.sub(r" sr_end\(s,.*?;", "", raw)
            raw = re.sub(r"if \(sr_aot_return_boundary_begin\(.*?\)\) return; ", "", raw)
            raw = raw.replace(" SR_TAIL_DRAIN(s); if (sr_aot_return_boundary_end(s)) return;", "")
            if raw.strip(): compact.append(raw)
        if args.calls_only:
            compact = [line for line in compact if re.search(r"f_[0-9a-f]{8}\(s\)|sr_tail_record|dispatch_call_checked|SR_CODE_POINTER", line)]
            print("SYNTACTIC CALL SITES (conditions and dynamic targets require the full source):")
        print("\n".join(compact[args.offset:args.offset + args.limit]))
        if len(compact) > args.offset + args.limit: print(f"... {len(compact) - args.offset - args.limit} more lines")
print("DIRECT CALL / TAIL REFERENCES (not dynamic-call reachability):")
for name, path, line, body in functions:
    if name != target and re.search(r"\bf_" + target + r"(?:\(s\)|,)", body):
        print(f"  {name} {path.relative_to(DEV)}:{line}")
