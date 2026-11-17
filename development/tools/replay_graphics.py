"""Render a private captured GE frame through software and Vulkan, preserving all outputs."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "development"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--first-bad-draw", action="store_true")
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    if not fixture.is_relative_to(DEV / "tests/runs") or not fixture.is_file():
        parser.error("Use a private project probe's captured frame.ngef")
    exe = DEV / "generated/ge-replay/ge_replay.exe"
    build = json.loads(exe.with_suffix(".build.json").read_text(encoding="utf-8"))
    if sha(exe) != build["executable_sha256"]:
        raise SystemExit("Graphics replay executable does not match its build record")
    output = DEV / "tests/graphics-replay" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True)
    cases = [("software", 1)] + [("vulkan", scale) for scale in (1, 4, 8)]
    results = []
    for backend, scale in cases:
        label = f"{backend}-{scale}x"
        case = output / label
        case.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SR_", "PSP_"))}
        env.update(PATH=str(DEV / "toolchain/msys64/ucrt64/bin") + os.pathsep + env["PATH"],
            SR_RESOLUTION_SCALE=str(scale), SR_WINDOW_HIDDEN="1", SR_GPU_STATS="1",
            SR_USER_DATA_ROOT=str(case / "user"), SR_MOJIN_WINDOW_PUMP="cooperative",
            PSP_VFPU_TABLES=str(DEV / "third_party/nakagawa/assets/vfpu"))
        command = [str(exe), str(fixture), "--backend", backend, "--output", str(case / "frame.ppm")]
        with (case / "stdout.log").open("wb") as stdout, (case / "stderr.log").open("wb") as stderr:
            result = subprocess.run(command, cwd=case, env=env, stdout=stdout, stderr=stderr, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        row = dict(label=label, command=command, exit_code=result.returncode,
                   environment={k: v for k, v in env.items() if k.startswith(("SR_", "PSP_"))})
        frame = case / "frame.ppm"
        if result.returncode == 0 and frame.is_file():
            row["output_sha256"] = sha(frame)
            with Image.open(frame) as image:
                row["output_dimensions"] = list(image.size)
                image.save(frame.with_suffix(".png"))
        results.append(row)
        print(f"{label}: exit {result.returncode}", flush=True)
    if args.first_bad_draw:
        case = output / "first-bad-draw"
        case.mkdir()
        env["SR_RESOLUTION_SCALE"] = "1"
        env["SR_USER_DATA_ROOT"] = str(case / "user")
        command = [str(exe), str(fixture), "--first-bad-draw", "--mode", "auto", "--report", str(case / "report")]
        with (case / "stdout.log").open("wb") as stdout, (case / "stderr.log").open("wb") as stderr:
            result = subprocess.run(command, cwd=case, env=env, stdout=stdout, stderr=stderr, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        results.append(dict(label="first-bad-draw", command=command, exit_code=result.returncode))
        print(f"first-bad-draw: exit {result.returncode}", flush=True)
    record = dict(fixture=str(fixture), fixture_sha256=sha(fixture), build=build, cases=results,
        boundaries=["This tool processes captured GE commands; it executes no game MIPS CPU instructions.",
            "The built-in software rasterizer is a comparison reference, not PSP hardware evidence.",
            "Replays export guest-size 480x272 VRAM readback even when the GPU internally renders at 4x/8x.",
            "A capture may contain prior-frame framebuffer pixels; differences before this frame are not isolated by this test."])
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
