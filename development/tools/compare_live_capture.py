"""Measure replay/live image differences without treating a nearest frame as proof of fidelity."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    run, replay = args.run.resolve(), args.replay.resolve()
    if not run.is_relative_to(ROOT / "development/tests/runs") or not replay.is_relative_to(ROOT / "development/tests/graphics-replay"):
        parser.error("Use project-private probe and replay folders")
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    replay_meta = json.loads((replay / "result.json").read_text(encoding="utf-8"))
    if sha(run / "frame.ngef") != replay_meta["fixture_sha256"]:
        parser.error("The replay did not use this capture")
    reference_path = replay / "vulkan-1x/frame.ppm"
    reference = Image.open(reference_path).convert("RGB")
    rows = []
    for snapshot in meta.get("snapshots", []):
        path = run / snapshot["path"]
        live = Image.open(path).convert("RGB")
        if live.size != reference.size:
            parser.error("Only equal-size live and replay images can be compared; no resampling is implicit")
        diff = ImageChops.difference(live, reference)
        stats = ImageStat.Stat(diff)
        count = sum(max(pixel) > 2 for pixel in diff.getdata())
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), vblank=snapshot["vblank"],
                         mean_abs_rgb=sum(stats.mean) / 3, max_channel_diff=max(pair[1] for pair in stats.extrema),
                         pixels_over_2=count, pixel_count=live.width * live.height, bbox=diff.getbbox()))
    rows.sort(key=lambda row: row["mean_abs_rgb"])
    record = dict(live_run=run.relative_to(ROOT).as_posix(), executable_sha256=meta["executable_sha256"],
        fixture_sha256=replay_meta["fixture_sha256"], replay_executable_sha256=replay_meta["build"]["executable_sha256"],
        replay_image_sha256=sha(reference_path), images_sorted_by_mean_difference=rows,
        boundaries=["Nearest image is not by itself proof of matching GE/display frame boundaries.",
                    "Exact equality, where present, applies only to this captured frame and this backend/scale.",
                    "This is capture/replay fidelity, not a PSP hardware or all-scene renderer validation."])
    (replay / "live-comparison.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(replay / "live-comparison.json"), closest=rows[0] if rows else None), indent=2))


if __name__ == "__main__":
    main()
