"""Compile the production carry arithmetic and check exact time conservation.

Use Fraction as an independent oracle, boundary/discontinuity cases, and optional
complete captured stock-clock runs. This is not gameplay acceptance.
"""
import argparse
import ctypes as c
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / 'development'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_runs', nargs='*', type=Path)
    args = parser.parse_args()
    directory = DEV / 'tests/step-clock' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    source = directory / 'bridge.c'
    source.write_text('#include "step_clock.h"\n'
        '__declspec(dllexport) int step(MojinStepClock *s, uint64_t p, uint64_t n, '
        'int32_t v, uint32_t old, int enabled, uint32_t *out) { '
        'return mojin_step_clock_update(s,p,n,v,old,enabled,out); }\n', encoding='ascii')
    gcc = DEV / 'toolchain/msys64/ucrt64/bin/gcc.exe'
    env = dict(os.environ, PATH=str(gcc.parent) + os.pathsep + os.environ['PATH'])
    dll = directory / 'step.dll'
    command = [str(gcc), '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
               '-I' + str(DEV / 'runtime'), str(source), '-o', str(dll)]
    subprocess.run(command, check=True, env=env)
    lib = c.CDLL(str(dll))

    class State(c.Structure):
        _fields_ = [('last_time', c.c_uint64), ('remainder', c.c_uint32),
                    ('speed', c.c_int32), ('active', c.c_int)]

    lib.step.argtypes = [c.POINTER(State), c.c_uint64, c.c_uint64, c.c_int32,
                         c.c_uint32, c.c_int, c.POINTER(c.c_uint32)]
    lib.step.restype = c.c_int

    def run(state, previous, now, speed=128, old=None, enabled=True):
        if old is None:
            old = ((now - previous) * 100 // 16667) * (speed * 32) // 12800
        out = c.c_uint32(0xdeadbeef)
        rc = lib.step(c.byref(state), previous, now, speed, old, enabled, c.byref(out))
        return rc, out.value

    # Conservation over a long irregular cadence, rather than checking copies
    # of each implementation expression. Fraction never uses the C remainder.
    rng = random.Random(329)
    state = State()
    previous = (1 << 32) - 10000  # cross the low-word wrap in a real 64-bit clock
    exact = Fraction(0)
    emitted = 0
    for _ in range(20000):
        delta = rng.randrange(2000, 25000)
        rc, value = run(state, previous, previous + delta)
        assert rc == 1
        exact += Fraction(delta * 128, 66668)
        emitted += value
        assert emitted == int(exact)
        assert Fraction(state.remainder, 66668) == exact - emitted
        previous += delta

    boundaries = []
    for name, prev, now, speed, old, enabled, rc_expected in [
        ('disabled', 1, 11112, 128, 21, False, 0),
        ('equal_time', 10, 10, 128, 0, True, 0),
        ('reversed_time', 20, 10, 128, 99, True, 0),
        ('long_pause', 1, 2000001, 128, 3000, True, 0),
        ('zero_speed', 1, 11112, 0, 0, True, 0),
        ('negative_speed', 1, 11112, -128, 0xffffffff, True, 0),
        ('outside_signed_short', 1, 11112, 32768, 0, True, 0),
        ('zero_step_fallback', 1, 101, 128, 0, True, 0),
        ('exact_clamp', 1, 66669, 128, 128, True, 0),
        ('long_frame_clamp', 1, 70001, 128, 134, True, 0),
        ('wrong_static_quotient', 1, 11112, 128, 22, True, -1),
    ]:
        state = State(1, 66667, 128, 1)
        rc, result = run(state, prev, now, speed, old, enabled)
        assert rc == rc_expected and result == old and not state.active and state.remainder == 0, name
        boundaries.append(name)

    for changed_speed, discontinuity in [(64, False), (128, True)]:
        state = State(100, 66667, 128, 1)
        previous = 200 if discontinuity else 100
        rc, result = run(state, previous, previous + 11111, changed_speed)
        assert rc == 1
        exact = Fraction(11111 * changed_speed, 66668)
        assert result == int(exact) and Fraction(state.remainder, 66668) == exact - result
    boundaries += ['speed_change_resets_fraction', 'discontinuity_resets_fraction']

    captures = []
    for supplied in args.stock_runs:
        path = supplied.resolve()
        assert path.is_relative_to(DEV / 'tests/runs')
        meta = json.loads((path / 'run.json').read_text(encoding='utf-8'))
        assert meta['exit_code'] == 0 and not meta['timed_out']
        assert 'SR_MOJIN_EXPERIMENTAL_STEP_CARRY' not in meta['environment']
        from analyze_frame_clock import complete_window
        with (path / 'loop.csv').open(newline='') as stream:
            rows, coverage = complete_window([r for r in csv.DictReader(stream) if r['pc'] == '08907d6c'], 'capture')
        assert {r['speed_factor'] for r in rows} == {'128'}
        state, total, exact = State(), 0, Fraction(0)
        for a, b in zip(rows, rows[1:]):
            previous, now = int(a['engine_time_us']), int(b['engine_time_us'])
            rc, result = run(state, previous, now, 128, int(b['step_i']))
            assert rc == 1, 'Capture contains a clamp/discontinuity; use a separate acceptance case'
            exact += Fraction((now - previous) * 128, 66668)
            total += result
            assert total == int(exact) and Fraction(state.remainder, 66668) == exact - total
        captures.append(dict(run=str(path.relative_to(ROOT)), intervals=len(rows)-1,
            trace_sha256=hashlib.sha256((path/'loop.csv').read_bytes()).hexdigest(),
            corrected_ticks=total, exact_ticks=float(exact), coverage=coverage))

    result = dict(passed=True, synthetic_intervals=20000, boundaries=boundaries, captures=captures,
        header_sha256=hashlib.sha256((DEV/'runtime/step_clock.h').read_bytes()).hexdigest(),
        dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest(), compiler=str(gcc), command=command,
        directory=str(directory.relative_to(ROOT)), limits='Arithmetic component only; no gameplay or static-callsite acceptance.')
    (DEV / 'evidence/step-clock-test.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
