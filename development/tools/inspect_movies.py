"""Read PSMF headers in place; do not extract or duplicate movie resources."""
import hashlib
import json
from pathlib import Path
from inspect_input import Iso

ROOT = Path(__file__).resolve().parents[2]
image = Iso(ROOT / "魔法禁书目录.iso")
rows = []
try:
    for entry in image.entries:
        if entry["directory"] or not entry["path"].upper().endswith(".PMF"):
            continue
        header = image.read(entry["offset"], min(2048, entry["size"]))
        if header[:4] != b"PSMF":
            raise ValueError(f"Unexpected movie header: {entry['path']}")
        first = int.from_bytes(header[0x54:0x5a], "big")
        last = int.from_bytes(header[0x5a:0x60], "big")
        rows.append(dict(path=entry["path"], iso_offset=entry["offset"], bytes=entry["size"],
            header_sha256=hashlib.sha256(header).hexdigest(), version=header[4:8].decode("ascii"),
            stream_offset=int.from_bytes(header[8:12], "big"), stream_bytes=int.from_bytes(header[12:16], "big"),
            first_timestamp=first, last_timestamp=last, header_duration_seconds=(last-first)/90000))
finally:
    image.file.close()
report = dict(scope="PSMF header metadata only, not complete decode/playback validation", movies=rows)
(ROOT / "development/evidence/movie-headers.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
for row in rows:
    print(f"{row['path']}: header duration {row['header_duration_seconds']:.3f} s; {row['bytes']} bytes")
