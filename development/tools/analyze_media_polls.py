"""Bind bounded movie-poll counters to actual new-frame intervals, not call latency."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    manifest = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if manifest["exit_code"] != 0 or manifest["timed_out"]:
        raise SystemExit("Requires a completed normal-exit run")
    with (run / "media-polls.csv").open(newline="") as f:
        polls = list(csv.DictReader(f))
    with (run / "frames.csv").open(newline="") as f:
        frames = list(csv.DictReader(f))
    if not polls or not frames:
        raise SystemExit("Missing observations")
    count_fields = ["available_calls", "zero_available", "put_calls", "put_packets",
                    "avc_au", "atrac_au", "avc_decode", "atrac_decode"]
    intervals = []
    for index in sorted(range(1, len(frames)), key=lambda i: float(frames[i]["work_ms"] or 0), reverse=True)[:5]:
        current, previous = frames[index], frames[index - 1]
        lo, hi = int(previous["vcount"]), int(current["vcount"])
        # Include both boundary buckets: coarse vblank counts do not prove that
        # every call in those buckets lies strictly between the two presents.
        rows = [r for r in polls if lo <= int(r["vcount"]) <= hi]
        counts = {key: sum(int(r[key]) for r in rows) for key in count_fields}
        intervals.append(dict(start_vcount=lo, end_vcount=hi, frame_metrics=current,
                              inclusive_boundary_bucket_counts=counts,
                              available_return_addresses=sorted({r["available_ra"] for r in rows if int(r["available_calls"])}),
                              available_thread_ids=sorted({r["available_uid"] for r in rows if int(r["available_calls"])}),
                              occupied_poll_buckets=len(rows)))
    report = dict(run=run.relative_to(ROOT).as_posix(), executable_sha256=manifest["executable_sha256"],
                  image_sha256=manifest["image_sha256"], exit_code=manifest["exit_code"],
                  inputs={name: digest(run / name) for name in ("run.json", "frames.csv", "media-polls.csv", "stderr.log")},
                  semantics="work_ms is cumulative host CPU work between distinct presented game frames, not the duration of one blocked call. guest_ms is nested runtime accounting. Counts include both boundary vblanks; no causal percentage is inferred.",
                  scope="First 4096 vblanks only; opt-in observational instrumentation. No claim of PSP equivalence or improved timing.",
                  totals={key: sum(int(r[key]) for r in polls) for key in count_fields},
                  largest_work_intervals=intervals)
    target = run / "media-poll-analysis.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=target.relative_to(ROOT).as_posix(), totals=report["totals"],
                          largest=intervals[0]), indent=2))


if __name__ == "__main__":
    main()
