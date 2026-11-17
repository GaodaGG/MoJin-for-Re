"""Verify the pinned upstream release; extract only its shared prerequisites."""
import hashlib
import argparse
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "development/downloads/nakagawa-recomp-0.0.3-windows-x64.zip"
EXPECTED = "af52764c7f25d55759cc05545aeb7bc7a6ca1f51aa223dc4ddb47d7bff760a0d"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-verified', type=Path, help='Hardlink an existing identical tool only after comparing it with the fixed archive bytes')
    args = parser.parse_args()
    shared = args.reuse_verified.resolve() if args.reuse_verified else None
    with ARCHIVE.open("rb") as f:
        actual = hashlib.file_digest(f, "sha256").hexdigest()
    if actual != EXPECTED:
        raise SystemExit(f"Release digest mismatch: {actual}")
    dest = ROOT / "development/toolchain"
    manifest = []
    reused = 0
    with zipfile.ZipFile(ARCHIVE) as z:
        for item in z.infolist():
            if not item.filename.startswith("prereqs/") or item.is_dir():
                continue
            rel = PurePosixPath(item.filename).relative_to("prereqs")
            if rel.is_absolute() or ".." in rel.parts or any(":" in p for p in rel.parts):
                raise ValueError("Unsafe archive member")
            out = dest.joinpath(*rel.parts)
            data = z.read(item)  # zipfile verifies CRC before returning.
            digest = hashlib.sha256(data).hexdigest()
            if out.exists() and hashlib.sha256(out.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Existing tool differs; preserve and investigate: {out}")
            if not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                existing = shared.joinpath(*rel.parts) if shared else None
                if existing and existing.is_file() and hashlib.sha256(existing.read_bytes()).hexdigest() == digest:
                    os.link(existing, out)
                    reused += 1
                else:
                    out.write_bytes(data)
            manifest.append(dict(path=rel.as_posix(), size=len(data), sha256=digest))
    evidence = ROOT / "development/evidence/toolchain-files.json"
    evidence.write_text(json.dumps(dict(archive_sha256=actual, files=manifest, reused_identical_files=reused), indent=2) + "\n", encoding="utf-8")
    print(f"Verified and restored {len(manifest)} toolchain files ({sum(x['size'] for x in manifest)} bytes); {reused} identical shared files")


if __name__ == "__main__":
    main()
