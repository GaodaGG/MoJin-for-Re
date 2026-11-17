"""Summarize captured presentation cadence; never equate it with game logic rate."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    values = sorted(values)
    def percentile(p):
        pos = (len(values) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    return dict(mean=statistics.fmean(values), median=statistics.median(values),
                p95=percentile(.95), p99=percentile(.99), maximum=values[-1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--vblank-range", required=True, help="Inclusive LO:HI; choose only observed scene coverage")
    parser.add_argument("--scope", required=True, help="Human description of observed scene and uncertainties")
    args = parser.parse_args()
    run = args.run.resolve()
    if not run.is_relative_to(ROOT / "development/tests/runs"):
        parser.error("Use a project-private run")
    lo, hi = map(int, args.vblank_range.split(":"))
    if not 0 <= lo <= hi:
        parser.error("Invalid vblank range")
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    with (run / "frames.csv").open(encoding="utf-8", newline="") as file:
        rows = [row for row in csv.DictReader(file) if lo <= int(row["vcount"]) <= hi]
    if not rows:
        parser.error("No frame intervals in the requested range")
    buckets = Counter(int(row["vblanks"]) for row in rows)
    metrics = {key: stats([float(row[key]) for row in rows])
               for key in rows[0] if key.endswith("_ms")}
    images = []
    for snapshot in meta.get("snapshots", []):
        path = run / snapshot["path"]
        with Image.open(path) as frame:
            images.append(dict(path=snapshot["path"], vblank=snapshot["vblank"],
                               width=frame.width, height=frame.height, sha256=digest(path)))
    slowest = sorted(rows, key=lambda row: float(row["wall_ms"]), reverse=True)[:12]
    result = dict(schema="mojin-render-observation-v1", run=run.relative_to(ROOT).as_posix(),
        scope=args.scope, executable_sha256=meta["executable_sha256"],
        image_sha256=meta["image_sha256"], run_manifest_sha256=digest(run / "run.json"),
        frames_csv_sha256=digest(run / "frames.csv"), environment=meta["environment"],
        exit_code=meta["exit_code"], timed_out=meta["timed_out"],
        vblank_range=[lo, hi], measured_interval_count=len(rows), vblank_intervals=dict(sorted(buckets.items())),
        measured_new_frame_rate=1000 / metrics["wall_ms"]["mean"], metrics_ms=metrics,
        slowest_intervals=slowest, captures=images,
        boundaries=["New framebuffer cadence does not prove animation/physics/cooldown/particle/movie logic rate.",
            "Metrics can overlap or span pipelined GPU work; do not sum them as exclusive wall-time buckets.",
            "Screen capture, traces, sound recording, user input and scene transitions can affect timing.",
            "AOT instruction-level profiling is disabled; aot_ms=0 in per-frame CSV does not imply no AOT work.",
            "Capture dimensions describe game composition, not physical monitor resolution or source texture detail."])
    execution = run / "execution-share.json"
    if execution.is_file():
        result["execution"] = json.loads(execution.read_text(encoding="utf-8"))
    target = run / "render-analysis.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(target), frames=len(rows), cadence=result["measured_new_frame_rate"],
        wall_ms=metrics["wall_ms"], gpu_ms=metrics["gpu_ms"], gaps=dict(buckets)), indent=2))


if __name__ == "__main__":
    main()
