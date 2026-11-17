"""Losslessly NTFS-compress only completed private probe captures, verifying every byte hash."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

from disk_usage import allocation, ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    files = []
    for path in args.runs:
        run = path.resolve()
        record_path = None
        if run.is_relative_to(ROOT / "development/tests/runs"):
            record_path = run / "run.json"
        elif run.is_relative_to(ROOT / "development/tests/settings-ui"):
            record_path = run / "result.json"
        if not record_path or not record_path.is_file() or "exit_code" not in json.loads(record_path.read_text(encoding="utf-8")):
            parser.error("Only completed project probes or settings UI tests are accepted")
        files += [p for p in run.iterdir() if p.is_file() and p.suffix in {".ppm", ".wav", ".ngef", ".bmp"}]
    if any(path.is_symlink() or path.is_junction() for path in files):
        parser.error("Links are not accepted")
    results = []
    for path in sorted(set(files)):
        before = sha(path)
        size_before = allocation(path)
        result = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/compact.exe"),
                                 "/c", "/i", "/q", str(path)], capture_output=True)
        after = sha(path)
        results.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=after,
            bytes=path.stat().st_size, allocated_before=size_before, allocated_after=allocation(path),
            command_exit=result.returncode, hash_verified=before == after))
        if before != after:
            raise SystemExit(f"Content changed unexpectedly: {path}; compression stopped")
    report = dict(method="NTFS transparent compression; decompression: compact /u <file>; no file deletion",
                  created_utc=datetime.now(timezone.utc).isoformat(), files=results,
                  saved_allocated_bytes=sum(r["allocated_before"] - r["allocated_after"] for r in results))
    target = ROOT / "development/evidence" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-probe-compression.json")
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(target), files=len(results), saved_bytes=report["saved_allocated_bytes"],
                         all_hashes_verified=all(r["hash_verified"] for r in results),
                         command_errors=sum(r["command_exit"] != 0 for r in results)), indent=2))


if __name__ == "__main__":
    main()
