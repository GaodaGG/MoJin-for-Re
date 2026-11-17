"""Regression: an indirect target after callable alignment padding, plus refusals."""
import importlib.util
import json
from pathlib import Path
import sys

DEV = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mojin_codegen", DEV / "tools/codegen.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)
import analyze
from test_codegen_entry_semantics import _synthetic_elf

out = DEV / "build/entry-proof-test"
out.mkdir(parents=True, exist_ok=True)
entry, pad, target = 0x10000, 0x10008, 0x1000c
words = {entry: 0x03e00008, entry+4: 0, pad: 0,
         target: 0x25290001, target+4: 0x01000008, target+8: 0}


def image(name, changes):
    path = out / (name + ".elf")
    path.write_bytes(_synthetic_elf({**words, **changes}, entry))
    return analyze.Elf(str(path))


elf = image("leading-nop", {})
before = {}
analyze.analyze(elf, seeds={target}, report=before, seed_check=cg.upstream.emitter_seed_check(elf))
assert before["miss_seeds"][target].startswith("not-callable:"), before
after = {}
entries, ranges = cg.upstream.analyze(elf, seeds={target}, report=after,
                                    seed_check=cg.upstream.emitter_seed_check(elf))
assert after["miss_seeds"][target] == "applied" and target in entries
assert cg.upstream.emitter_seed_check(elf)(entries, ranges)[target] is None
emitted = "\n".join(cg.upstream.emit_function(elf, target, ranges, set(entries)))
assert f"0x{target:08x}u" in emitted
assert f"sr_begin(s, 0x{pad:08x}u" not in emitted  # Do not execute padding as a workaround.

# The same missing entry after a state-changing instruction must remain refused.
for name, changes in [("non-nop-prefix", {pad: 0x25080001}),
                      ("unowned-frame-release", {target: 0x27bd0010}),
                      ("reserved-instruction", {target: 0x74786574})]:
    elf = image(name, changes)
    try:
        cg.upstream.analyze(elf, seeds={target}, report={},
                            seed_check=cg.upstream.emitter_seed_check(elf))
    except ValueError as exc:
        assert "Requested static entries were refused" in str(exc), str(exc)
    else:
        raise AssertionError(f"Unsafe entry accepted: {name}")

result = dict(passed=True, synthetic_cases=4, baseline_refuses_valid_padding_target=True,
              corrected_emission_skips_padding=True, negative_entries_refused=True,
              scope="Analyzer and real C emitter; game replay is a separate validation")
(DEV / "evidence/entry-proof-test.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
