"""Compare bounded update-clock feasibility probes, without certifying gameplay timing."""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re
import statistics
import struct

DEV = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def float_bits(bits):
    return struct.unpack('<f', int(bits, 16).to_bytes(4, 'little'))[0]


def summarize(run):
    meta = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    assert meta['exit_code'] == 0 and not meta['timed_out'], 'Normal exit required'
    assert sha(Path(meta['command'][0])) == meta['executable_sha256']
    log = (run / 'stderr.log').read_text(encoding='utf-8', errors='replace')
    trace = re.search(r'MOJIN_LOOP_TRACE rows=(\d+) dropped=(\d+) write_error=(\d+)', log)
    assert trace and trace.groups()[1:] == ('0', '0')
    clock = re.search(r'MOJIN_FRAME_CLOCK target=(\d+) calls=(\d+) late=(\d+) errors=(\d+)', log)
    if clock:
        assert int(clock[2]) > 0 and clock[4] == '0', 'Experiment did not activate cleanly'
    target = meta['environment'].get('SR_MOJIN_EXPERIMENTAL_UPDATE_RATE')
    assert bool(target) == bool(clock)
    if target:
        assert int(target) == int(clock[1])
    input_log = re.search(r'MOJIN_FRAME_INPUT mode=peek calls=(\d+) repeated_samples=(\d+) errors=(\d+)', log)
    input_requested = meta['environment'].get('SR_MOJIN_EXPERIMENTAL_INPUT_PEEK') == '1'
    assert input_requested == bool(input_log)
    if input_log:
        assert int(input_log[1]) > 0 and input_log[3] == '0'
    execution = json.loads((run / 'execution-share.json').read_text(encoding='utf-8'))
    assert execution['interp_entries'] == 0 and execution['miss_targets'] == 0
    with (run / 'loop.csv').open(newline='') as stream:
        all_rows = list(csv.DictReader(stream))
    assert len(all_rows) == int(trace[1])
    rows = [r for r in all_rows if r['pc'] == '08907d6c' and 7600 <= int(r['vcount']) <= 8800]
    assert len(rows) > 2 and {r['scene_callback'] for r in rows} == {'0885f978'}
    elapsed = (int(rows[-1]['host_ns']) - int(rows[0]['host_ns'])) / 1e9
    sites = ['08907c44', '08907d6c', '0891d368']
    phases = [r for r in all_rows if r['pc'] in sites and 7600 <= int(r['vcount']) <= 8800]
    phase_times = {}
    for a, b in zip(sites, sites[1:] + sites[:1]):
        spans = [(int(y['host_ns']) - int(x['host_ns'])) / 1e6
                 for x, y in itertools.pairwise(phases) if x['pc'] == a and y['pc'] == b]
        assert spans
        phase_times[a + '->' + b] = dict(count=len(spans), median=statistics.median(spans),
                                        minimum=min(spans), maximum=max(spans))
    dense_sites = {
        '0891d318': 'before next-loop prelude', '0891d320': 'before title input processing',
        '0891d730': 'before controller read/peek', '0891d738': 'after controller return',
        '0891d36c': 'before post-update callback', '0891d374': 'before command generation',
        '0891d3d8': 'before common frame end', '0891d410': 'before alternate frame end',
        '0891bf54': 'before graphics completion call', '0891bf68': 'before frame wait',
        '0891bf70': 'after wait, before system-time read',
        '0891d3e0': 'before next command-list setup', '0891d418': 'before alternate setup',
        '0891d3e8': 'after setup return', '0891d420': 'after alternate setup return',
    }
    dense = [r for r in all_rows if r['pc'] in dense_sites or r['pc'] in sites]
    dense_spans = {}
    for x, y in itertools.pairwise(dense):
        if not (7600 <= int(x['vcount']) <= int(y['vcount']) <= 8800):
            continue
        assert x['uid'] == y['uid'], 'Do not mix threads in call-boundary timing'
        key = x['pc'] + '->' + y['pc']
        dense_spans.setdefault(key, []).append((int(y['host_ns']) - int(x['host_ns'])) / 1e6)
    dense_times = {k: dict(count=len(v), median=statistics.median(v), minimum=min(v), maximum=max(v))
                   for k, v in dense_spans.items()}
    with (run / 'frames.csv').open(newline='') as stream:
        frames = [r for r in csv.DictReader(stream) if 7600 <= int(r['vcount']) <= 8800]
    frame_wall = sum(float(r['wall_ms']) for r in frames) / 1000
    assert len(frames) > 2 and frame_wall > 0
    states = []
    valid = [r for r in rows if r.get('battle_valid') == '1']
    for key, block in itertools.groupby(valid, key=lambda r: (r['battle_object'], r['battle_state'], r['battle_handler'])):
        block = list(block)
        if len(block) < 2:
            continue
        span = (int(block[-1]['host_ns']) - int(block[0]['host_ns'])) / 1e9
        states.append(dict(object=key[0], state=int(key[1]), handler=key[2], samples=len(block), host_seconds=span,
                           calls_delta=int(block[-1]['battle_calls']) - int(block[0]['battle_calls']),
                           ticks_delta=int(block[-1]['battle_ticks']) - int(block[0]['battle_ticks'])))
    input_fields = None
    if 'input_buttons' in rows[0]:
        input_fields = dict(held_masks=dict(Counter(r['input_buttons'] for r in rows)),
                            pressed_masks=dict(Counter(r['input_pressed'] for r in rows)),
                            stick_masks=dict(Counter(r['stick_direction'] for r in rows)),
                            stick_pressed_masks=dict(Counter(r['stick_pressed'] for r in rows)),
                            history_step_mod64=dict(Counter((int(b['input_history_index'])-int(a['input_history_index'])) % 64
                                                          for a,b in itertools.pairwise(rows))),
                            note='Idle route has no scripted presses in this interval; this alone does not verify edge or analog behavior.')
    return dict(run=str(run.relative_to(DEV)), executable_sha256=meta['executable_sha256'],
                image_sha256=meta['image_sha256'], input_script_sha256=meta['input_script_sha256'],
                hashes={name: sha(run / name) for name in ('run.json','build.json','input.pad','loop.csv','frames.csv','stderr.log','execution-share.json')},
                requested_update_rate=int(target) if target else 'original', window=[7600,8800],
                experimental_input_peek=input_requested,
                input_poll=dict(calls=int(input_log[1]), repeated_samples=int(input_log[2]), errors=int(input_log[3])) if input_log else None,
                active_experiment_calls=int(clock[2]) if clock else 0,
                missed_deadlines=int(clock[3]) if clock else 0,
                actual_vcount_bounds=[int(rows[0]['vcount']), int(rows[-1]['vcount'])],
                update_count=len(rows), elapsed_seconds=elapsed,
                update_intervals_per_second=(len(rows)-1)/elapsed,
                phase_interval_ms=phase_times,
                dense_observation_sites=dense_sites,
                dense_adjacent_interval_ms=dense_times,
                observed_vblank_rate=(int(rows[-1]['vcount'])-int(rows[0]['vcount']))/elapsed,
                vblank_step_counts=dict(Counter(int(b['vcount'])-int(a['vcount']) for a,b in itertools.pairwise(rows))),
                distinct_frames=len(frames), distinct_frame_intervals_per_second=len(frames)/frame_wall,
                frame_interval_vblank_counts=dict(Counter(r['vblanks'] for r in frames)),
                step_counts=dict(Counter(r['step_i'] for r in rows)),
                accumulator_seconds=float_bits(rows[-1]['time_s_bits'])-float_bits(rows[0]['time_s_bits']),
                observed_state_samples=len(valid),
                observed_input_fields=input_fields,
                longest_state_segment=max(states, key=lambda x:x['host_seconds']) if states else None,
                limits=['Training idle route and one bounded interval only; no whole-game acceptance.',
                        'Update and distinct-frame counts are not physical display refresh measurements.',
                        'No proof yet of movement/particles/animation/physics/cooldown/film time equivalence.',
                        'State-field names are provisional; clock-field agreement alone cannot certify gameplay.',
                        'Includes tracing and sparse capture overhead; driver cache is not cleared.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+')
    args = parser.parse_args()
    result = [summarize(p.resolve()) for p in args.runs]
    for supplied, row in zip(args.runs, result):
        (supplied / 'frame-clock-analysis.json').write_text(json.dumps(row, indent=2)+'\n', encoding='utf-8')
    for r in result:
        print(json.dumps({k:r[k] for k in ('run','requested_update_rate','active_experiment_calls','missed_deadlines',
                                         'update_intervals_per_second','observed_vblank_rate','distinct_frame_intervals_per_second',
                                         'accumulator_seconds','longest_state_segment')}, indent=2))


if __name__ == '__main__':
    main()
