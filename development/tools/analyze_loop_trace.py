"""Summarize opt-in main-loop observations; this does not certify high-FPS game timing."""
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
PHASES = ("0880a620", "0880a62c", "0880a638", "0880a644")
UPDATES = ("08907c44", "08907d6c", "0891d368")


def float_bits(value):
    return struct.unpack("<f", int(value, 16).to_bytes(4, "little"))[0]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--window", default="7600:11000", help="Inclusive guest-vblank observation window")
    args = parser.parse_args()
    lo, hi = map(int, args.window.split(":"))
    if not 0 <= lo < hi:
        parser.error("window must increase")
    run = args.run.resolve()
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    log = (run / "stderr.log").read_text(encoding="utf-8", errors="replace")
    assert meta["exit_code"] == 0 and not meta["timed_out"], "Normal exit required"
    final = re.search(r"MOJIN_LOOP_TRACE rows=(\d+) dropped=(\d+) write_error=(\d+)", log)
    assert final and final.groups()[1:] == ("0", "0"), "Missing, truncated or failed observation output"
    exe = Path(meta["command"][0])
    assert digest(exe) == meta["executable_sha256"], "Executable drift"
    execution = json.loads((run / "execution-share.json").read_text(encoding="utf-8"))
    assert execution["interp_entries"] == 0 and execution["miss_targets"] == 0
    with (run / "loop.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == int(final[1]) and rows, "Trace row count differs"
    for i, row in enumerate(rows):
        assert int(row["seq"]) == i
        assert row["pc"] in PHASES + UPDATES, "Unknown observation site"
        if i:
            assert int(row["host_ns"]) >= int(rows[i - 1]["host_ns"])
    auxiliary = [r for r in rows if r["pc"] in PHASES]
    assert all(r["pc"] == PHASES[i % 4] for i, r in enumerate(auxiliary)), "Auxiliary loop order changed"
    primary_pc = UPDATES[1] if any(r["pc"] == UPDATES[1] for r in rows) else PHASES[0]
    phases = [r for r in rows if r["pc"] == primary_pc]
    selected = [r for r in phases if lo <= int(r["vcount"]) <= hi]
    if not selected:
        result = dict(status="requested_window_not_observed", window=[lo, hi],
                      executable_sha256=meta["executable_sha256"], image_sha256=meta["image_sha256"],
                      trace_sha256=digest(run / "loop.csv"), all_rows=len(rows),
                      observed_vcount_range=[int(rows[0]["vcount"]), int(rows[-1]["vcount"])],
                      callbacks=dict(Counter(r["callback"] for r in phases)),
                      conclusion="This thread's loop ends before the battle window; do not use it as a gameplay update-rate measurement.")
        (run / "loop-analysis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return
    assert len(selected) > 2, "Window has insufficient loop observations"
    deltas = [(int(b["host_ns"]) - int(a["host_ns"])) / 1e6
              for a, b in itertools.pairwise(selected)]
    elapsed = (int(selected[-1]["host_ns"]) - int(selected[0]["host_ns"])) / 1e9
    intervals = [int(b["vcount"]) - int(a["vcount"]) for a, b in itertools.pairwise(selected)]
    engine_steps = [int(b["engine_frame"]) - int(a["engine_frame"]) for a, b in itertools.pairwise(selected)]
    segments = []
    callback_key = "scene_callback" if primary_pc == UPDATES[1] else "callback"
    for key, group in itertools.groupby(phases, key=lambda r: (r[callback_key], r["state"], r["uid"])):
        block = list(group)
        segments.append(dict(callback=key[0], state=int(key[1]), uid=key[2],
                             first_vcount=int(block[0]["vcount"]), last_vcount=int(block[-1]["vcount"]),
                             observations=len(block)))
    with (run / "frames.csv").open(newline="") as stream:
        frames = [r for r in csv.DictReader(stream) if lo <= int(r["vcount"]) <= hi]
    wall_ms = sum(float(r["wall_ms"]) for r in frames)
    result = dict(
        run=str(run.relative_to(DEV)), executable_sha256=meta["executable_sha256"],
        image_sha256=meta["image_sha256"], input_script_sha256=meta.get("input_script_sha256"),
        evidence_sha256={name: digest(run / name) for name in
                        ("run.json", "build.json", "loop.csv", "frames.csv", "stderr.log", "input.pad", "execution-share.json")},
        observation_sites={PHASES[0]: "before callback argument 5", PHASES[1]: "before argument 6",
                           PHASES[2]: "before argument 7", PHASES[3]: "after frame-end / vblank wait",
                           UPDATES[0]: "common update entry", UPDATES[1]: "before title update callback after timing calculation",
                           UPDATES[2]: "common update returned to engine loop"},
        primary_pc=primary_pc, all_rows=len(rows), all_site_counts=dict(Counter(r["pc"] for r in rows)),
        final_auxiliary_partial_phases=len(auxiliary) % 4, auxiliary_ordered_phases=True,
        window=[lo, hi], actual_loop_window=[int(selected[0]["vcount"]), int(selected[-1]["vcount"])],
        loop_observations=len(selected), host_elapsed_seconds=elapsed,
        loop_intervals_per_second=(len(selected) - 1) / elapsed,
        loop_interval_ms=dict(min=min(deltas), median=statistics.median(deltas), max=max(deltas)),
        vblank_step_histogram=dict(Counter(intervals)), engine_counter_step_histogram=dict(Counter(engine_steps)),
        callback_counts=dict(Counter(r[callback_key] for r in selected)),
        distinct_frame_telemetry=dict(rows=len(frames), wall_seconds=wall_ms / 1000,
                                      intervals_per_second=len(frames) * 1000 / wall_ms,
                                      vblank_step_histogram=dict(Counter(r["vblanks"] for r in frames))),
        callback_state_segments=segments,
        limits=["Read-only diagnostic overhead is included.",
                "Loop calls and distinct-frame telemetry do not prove every gameplay subsystem updates at this rate.",
                "Callback argument labels are observed dispatch stages, not asserted physics/render semantics.",
                "No 90/120 Hz changes or character/particle/physics/cooldown time-equivalence proof.",
                "Window bounds use guest vblanks; frame telemetry includes intervals crossing its first boundary."])
    if primary_pc == UPDATES[1]:
        accumulated = float_bits(selected[-1]["time_s_bits"]) - float_bits(selected[0]["time_s_bits"])
        integrated = sum(float_bits(r["step_f_bits"]) / 1920 for r in selected[1:])
        result["observed_engine_fields"] = dict(
            update_count_steps=dict(Counter(int(b["update_count"]) - int(a["update_count"]) for a, b in itertools.pairwise(selected))),
            integer_step_counts=dict(Counter(r["step_i"] for r in selected)),
            float_step_counts=dict(Counter(str(float_bits(r["step_f_bits"])) for r in selected)),
            frame_step_counts=dict(Counter(str(float_bits(r["step_frame_bits"])) for r in selected)),
            whole_tick_counts=dict(Counter(r["whole_ticks"] for r in selected)),
            time_accumulator_advance=accumulated,
            integrated_step_over_1920=integrated,
            accumulation_float_rounding_difference=accumulated - integrated,
            normalized_step_matches=all(float_bits(r["step_frame_bits"]) == float_bits(r["step_f_bits"]) / 32 for r in selected),
            note="Exact fields from f_08907c44; consumer coverage and physical semantics still require proof.")
    target = run / "loop-analysis.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("run", "all_rows", "loop_observations", "loop_intervals_per_second",
                                          "loop_interval_ms", "vblank_step_histogram", "callback_counts",
                                          "distinct_frame_telemetry")}, indent=2))


if __name__ == "__main__":
    main()
