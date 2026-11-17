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


def complete_window(samples, label, start=7600, end=8800):
    """Require evidence on both sides; a normal early exit is not a full test."""
    counts = [int(r['vcount']) for r in samples]
    if not counts or counts[0] >= start or counts[-1] <= end:
        raise ValueError(f'{label}: incomplete observation window {start}:{end}; '
                         f'available {counts[0] if counts else None}:{counts[-1] if counts else None}')
    if any(b < a for a, b in itertools.pairwise(counts)):
        raise ValueError(f'{label}: vcount reversed; cannot combine observation epochs')
    window = [r for r in samples if start <= int(r['vcount']) <= end]
    if len(window) < 3 or int(window[0]['vcount']) > start + 1 or int(window[-1]['vcount']) < end - 1:
        raise ValueError(f'{label}: samples do not reach both window boundaries')
    return window, dict(requested=[start, end], available=[counts[0], counts[-1]],
                        sampled=[int(window[0]['vcount']), int(window[-1]['vcount'])],
                        bracketed=True)


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
    game_mode = meta['environment'].get('SR_MOJIN_GAME_FPS') == '120'
    target = '120' if game_mode else meta['environment'].get('SR_MOJIN_EXPERIMENTAL_UPDATE_RATE')
    assert bool(target) == bool(clock)
    if target:
        assert int(target) == int(clock[1])
    input_log = re.search(r'MOJIN_FRAME_INPUT mode=peek calls=(\d+) repeated_samples=(\d+) errors=(\d+)', log)
    input_requested = game_mode or meta['environment'].get('SR_MOJIN_EXPERIMENTAL_INPUT_PEEK') == '1'
    assert input_requested == bool(input_log)
    if input_log:
        assert int(input_log[1]) > 0 and input_log[3] == '0'
    step_requested = game_mode or meta['environment'].get('SR_MOJIN_EXPERIMENTAL_STEP_CARRY') == '1'
    step_log = re.search(r'MOJIN_STEP_CARRY calls=(\d+) applied=(\d+) bypassed=(\d+) errors=(\d+) original_ticks=(\d+) corrected_ticks=(\d+) denominator=(\d+)', log)
    assert step_requested == bool(step_log), 'Requested step correction was not observed'
    if step_log:
        assert target and input_requested and int(step_log[2]) > 0 and step_log[4] == '0'
        assert int(step_log[1]) == int(step_log[2]) + int(step_log[3]) and step_log[7] == '66668'
    execution = json.loads((run / 'execution-share.json').read_text(encoding='utf-8'))
    assert execution['interp_entries'] == 0 and execution['miss_targets'] == 0
    with (run / 'loop.csv').open(newline='') as stream:
        all_rows = list(csv.DictReader(stream))
    assert len(all_rows) == int(trace[1])
    assert [int(r['seq']) for r in all_rows] == list(range(len(all_rows))), 'Missing/reordered trace rows'
    assert all(int(b['host_ns']) >= int(a['host_ns']) for a,b in itertools.pairwise(all_rows)), 'Host time reversed'
    gate_check = None
    if all_rows and 'step_fraction' in all_rows[0]:
        updates = [r for r in all_rows if r['pc'] == '08907d6c']
        # Leave one vblank at each edge for a step calculated in the preceding
        # frame end to reach the next update. Outside it, all carry state is reset.
        if game_mode:
            outside = [b for a,b in itertools.pairwise(updates)
                       if a['scene_callback'] != '0885f978' and b['scene_callback'] != '0885f978']
        else:
            outside = [r for r in updates if not step_requested or int(r['vcount']) < 7399 or int(r['vcount']) > 9000]
        assert outside and all(int(r['step_fraction']) == 0xffffffff for r in outside), 'Correction leaked outside its opt-in window'
        gate_check = dict(inactive_samples=len(outside), all_inactive=True)
    rows, update_coverage = complete_window([r for r in all_rows if r['pc'] == '08907d6c'], 'updates')
    assert len(rows) > 2 and {r['scene_callback'] for r in rows} == {'0885f978'}
    assert {r['state'] for r in rows} == {'3'} and len({r['uid'] for r in rows}) == 1
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
        frames, frame_coverage = complete_window(list(csv.DictReader(stream)), 'frames')
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
                            note='Input-mask observations; compare the recorded input.pad before interpreting edge and hold counts.')
    arithmetic = None
    if 'engine_time_us' in rows[0]:
        predictions = []
        speed_resets = 0
        for a,b in itertools.pairwise(rows):
            delta = int(b['engine_time_us']) - int(a['engine_time_us'])
            speed = int(b['speed_factor'])
            assert delta > 0 and speed > 0, 'Unsupported time/speed regime for this arithmetic analysis'
            assert float_bits(b['step_override_bits']) <= 0, 'Positive common-step override needs separate analysis'
            assert float_bits(b['step_f_bits']) == int(b['step_i']), 'Integer and floating game steps disagree'
            assert float_bits(b['step_frame_bits']) == int(b['step_i']) / 32, 'Per-frame scale did not consume the same step'
            percent = delta * 100 // 16667
            quantized = percent * (speed << 5) // 12800
            expected = 32 if quantized <= 0 else min(128, quantized)
            corrected = expected
            if step_requested:
                previous_fraction, actual_fraction = int(a['step_fraction']), int(b['step_fraction'])
                assert 0 <= previous_fraction < 66668 and 0 <= actual_fraction < 66668, 'Inactive/bypassed carry in observation window'
                if speed != int(a['speed_factor']):
                    # Production resets the fraction when the title changes
                    # speed (e.g. hit stop). Verify that boundary explicitly.
                    previous_fraction = 0
                    speed_resets += 1
                corrected, remainder = divmod(delta * speed + previous_fraction, 66668)
                assert remainder == actual_fraction, 'Fraction was not conserved'
                assert corrected == int(b['step_i']), 'Generated step differs from carried arithmetic'
            predictions.append(dict(delta_us=delta, speed=speed, expected=expected,
                                    corrected=corrected, actual=int(b['step_i']), ideal=delta*100*(speed<<5)/(16667*12800)))
        arithmetic = dict(samples=len(predictions),
            speed_values=dict(Counter(r['speed_factor'] for r in rows)),
            exact_integer_formula_matches=sum(x['expected']==x['actual'] for x in predictions),
            selected_model_matches=sum(x['corrected']==x['actual'] for x in predictions),
            selected_model='fractional-carry' if step_requested else 'stock-two-divisions',
            expected_step_sum=sum(x['expected'] for x in predictions),
            observed_step_sum=sum(x['actual'] for x in predictions),
            unrounded_step_sum=sum(x['ideal'] for x in predictions),
            engine_elapsed_seconds=sum(x['delta_us'] for x in predictions)/1e6,
            integer_step_seconds=sum(x['actual'] for x in predictions)/1920,
            unrounded_step_seconds=sum(x['ideal'] for x in predictions)/1920,
            formula=('divmod(delta_us*speed_i16+previous_remainder,66668) within the supported positive unclamped window'
                     if step_requested else 'clamp_or_fallback(floor(floor(delta_us*100/16667)*(speed_i16<<5)/12800))'),
            expected_step_sum_meaning='Counterfactual stock two-division step sum; observed_step_sum is the actual game result.',
            note='Pinned positive-speed arithmetic only; does not certify consumers or gameplay speed.')
        if step_requested:
            arithmetic['fractional_ticks_error'] = arithmetic['observed_step_sum'] - arithmetic['unrounded_step_sum']
            arithmetic['verified_speed_resets'] = speed_resets
            # Each independently verified reset may discard less than one tick.
            assert -(speed_resets+1.0000001) < arithmetic['fractional_ticks_error'] < 1.0000001, 'Unexplained cumulative truncation'
            arithmetic['remainder_verified_each_interval'] = True
        arithmetic['integer_float_and_frame_steps_agree'] = True
    return dict(run=str(run.relative_to(DEV)), analyzer_sha256=sha(Path(__file__)), executable_sha256=meta['executable_sha256'],
                image_sha256=meta['image_sha256'], input_script_sha256=meta['input_script_sha256'],
                hashes={name: sha(run / name) for name in ('run.json','build.json','input.pad','loop.csv','frames.csv','stderr.log','execution-share.json')},
                requested_update_rate=int(target) if target else 'original', window=[7600,8800],
                coverage=dict(updates=update_coverage, frames=frame_coverage),
                clock_arithmetic=arithmetic,
                experimental_input_peek=input_requested,
                experimental_step_carry=step_requested,
                step_carry_gate=gate_check,
                step_carry_counts=dict(zip(('calls','applied','bypassed','errors','original_ticks','corrected_ticks','denominator'),
                                          map(int,step_log.groups()))) if step_log else None,
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
