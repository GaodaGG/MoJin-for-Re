"""Compare the observed AU clocks and startup cadence of two version-bound runs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read_run(run):
    run = run.resolve()
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert meta["exit_code"] == 0 and not meta["timed_out"]
    exe = Path(meta["command"][0])
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == meta["executable_sha256"]
    log = (run / "stderr.log").read_text(encoding="utf-8", errors="replace")
    assert "interp_entries=0 entries_dispatch_miss=0" in log
    movies, current = [], None
    for line in log.splitlines():
        opened = re.search(r"HLE_IoOpen: opening 'disc0:/PSP_GAME/USRDIR/([^']+\.PMF)'", line)
        if opened:
            current = dict(movie=opened[1], first_au={}, last_au={}, successful_au={}, pictures=None)
            movies.append(current)
        if not current:
            continue
        au = re.search(r"MOJIN_MEDIA api=(GetAvcAu|GetAtracAu) result=00000000 .* v=(\d+) .* pts=([0-9a-f]{16})", line)
        if au:
            key = au[1]
            value = dict(vcount=int(au[2]), pts=int(au[3], 16))
            current["first_au"].setdefault(key, value)
            current["last_au"][key] = value
            current["successful_au"][key] = current["successful_au"].get(key, 0) + 1
        if line.startswith("MPEG_PICTURES:"):
            current["pictures"] = dict(re.findall(r"(\w+)=(\S+)", line))
    with (run / "frames.csv").open(newline="") as f:
        frames = list(csv.DictReader(f))
    for movie in movies:
        if not movie["first_au"]:
            continue
        start = min(row["vcount"] for row in movie["first_au"].values())
        rows = [r for r in frames if start <= int(r["vcount"]) <= start + 90]
        movie["startup_90_vblank_window"] = dict(start=start, end=start + 90, frames=len(rows),
            maximum_cpu_work_ms=max(float(r["work_ms"] or 0) for r in rows),
            maximum_new_frame_interval_ms=max(float(r["wall_ms"]) for r in rows),
            maximum_vblank_span=max(int(r["vblanks"]) for r in rows))
    return dict(run=run.relative_to(ROOT).as_posix(), executable_sha256=meta["executable_sha256"],
                image_sha256=meta["image_sha256"], input_script=meta.get("input_script_sha256"),
                seconds=meta["elapsed_seconds"], movies=movies,
                file_hashes={name: hashlib.sha256((run / name).read_bytes()).hexdigest()
                             for name in ("run.json", "stderr.log", "frames.csv")})


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("before", type=Path)
parser.add_argument("after", type=Path)
parser.add_argument("--full-movies", action="store_true")
args = parser.parse_args()
before, after = read_run(args.before), read_run(args.after)
assert before["image_sha256"] == after["image_sha256"]
assert after["input_script"] is None, "Use natural movie playback for this timing check"
assert [m["movie"] for m in after["movies"][:2]] == ["AMW.PMF", "OP.PMF"]
for movie in before["movies"][:2]:
    assert movie["first_au"]["GetAtracAu"]["pts"] == 351
    assert movie["first_au"]["GetAvcAu"]["pts"] == 90000
for movie in after["movies"][:2]:
    assert movie["first_au"]["GetAtracAu"]["pts"] == 90000
    assert movie["first_au"]["GetAvcAu"]["pts"] == 90000
    if args.full_movies:
        pictures = movie["pictures"]
        expected = {"AMW.PMF": 270, "OP.PMF": 3240}[movie["movie"]]
        assert pictures and pictures["reason"] == "delete"
        assert all(int(pictures[key]) == expected for key in ("units", "decoded", "delivered"))
        assert all(int(pictures[key]) == 0 for key in ("superseded", "stale", "rejected", "held"))
report = dict(passed=True, before=before, after=after, full_movie_counters_checked=args.full_movies,
              limitations="Runtime AU and decoder counters, not device-loopback A/V sync or PSP hardware comparison. Host CPU work is interval total. Do not infer whole-game coverage or uniform frame times.")
out = args.after / "media-clock-verification.json"
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(passed=True, output=str(out), before=before["movies"], after=after["movies"]), indent=2))
