"""Read-only ISO9660/PSF/ELF inventory. Does not extract game assets."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def psf(data):
    if data[:4] != b"\x00PSF":
        raise ValueError("Not a PARAM.SFO")
    _, version, keys, values, count = struct.unpack_from("<5I", data)
    result = {}
    for i in range(count):
        key, fmt, length, maximum, offset = struct.unpack_from("<HHIII", data, 20 + i * 16)
        name = data[keys + key:].split(b"\0", 1)[0].decode("utf-8", "replace")
        value = data[values + offset: values + offset + length]
        result[name] = struct.unpack("<I", value)[0] if fmt == 0x404 else value.rstrip(b"\0").decode("utf-8", "replace")
    return result


def elf(data):
    if data[:4] != b"\x7fELF":
        return None
    if data[4:6] != b"\x01\x01":
        return {"class": data[4], "encoding": data[5]}
    fields = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    typ, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, shstrndx = fields
    segments = []
    for i in range(phnum):
        typ_, off, va, pa, filesz, memsz, flags_, align = struct.unpack_from("<8I", data, phoff + i * phsize)
        segments.append(dict(type=hex(typ_), offset=off, vaddr=hex(va), paddr=hex(pa), file_size=filesz, memory_size=memsz, flags=hex(flags_), alignment=align))
    sections = []
    raw = [struct.unpack_from("<10I", data, shoff + i * shsize) for i in range(shnum)]
    strings = b""
    if shstrndx < len(raw):
        s = raw[shstrndx]
        strings = data[s[4]:s[4] + s[5]]
    for s in raw:
        name = strings[s[0]:].split(b"\0", 1)[0].decode("ascii", "replace")
        sections.append(dict(name=name, type=hex(s[1]), flags=hex(s[2]), address=hex(s[3]), offset=s[4], size=s[5], entry_size=s[9]))
    return dict(bits=32, endian="little", type=hex(typ), machine=machine, entry=hex(entry), flags=hex(flags), segments=segments, sections=sections)


class Iso:
    sector = 2048

    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        self.file = self.path.open("rb")
        self.pvd = self.read(16 * self.sector, self.sector)
        if self.pvd[:7] != b"\x01CD001\x01":
            raise ValueError("Not an ISO9660 primary volume at sector 16")
        self.block_size = struct.unpack_from("<H", self.pvd, 128)[0]
        if self.block_size != self.sector:
            raise ValueError(f"Unsupported block size {self.block_size}")
        self.entries = []
        self._visited = set()
        self.walk(self.record(self.pvd[156:]), "")

    def read(self, off, size):
        if off < 0 or size < 0 or off + size > self.size:
            raise ValueError(f"Extent outside image: {off:#x}+{size:#x} > {self.size:#x}")
        self.file.seek(off)
        data = self.file.read(size)
        if len(data) != size:
            raise ValueError("Short read")
        return data

    @staticmethod
    def record(data):
        name = data[33:33 + data[32]]
        extent, extent_be, size, size_be = struct.unpack_from("<IIII", data, 2)
        if extent != int.from_bytes(data[6:10], "big") or size != int.from_bytes(data[14:18], "big"):
            raise ValueError("ISO both-endian fields disagree")
        return dict(name=name.decode("ascii", "replace").split(";")[0], extent=extent,
                    size=size, directory=bool(data[25] & 2), flags=data[25],
                    recorded_time=list(data[18:25]))

    def walk(self, directory, parent):
        key = directory["extent"], directory["size"]
        if key in self._visited:
            raise ValueError("Repeated directory extent")
        self._visited.add(key)
        data = self.read(directory["extent"] * self.sector, directory["size"])
        pos = 0
        while pos < len(data):
            length = data[pos]
            if length == 0:
                pos = (pos // self.sector + 1) * self.sector
                continue
            if length < 34 or pos + length > len(data):
                raise ValueError("Invalid directory record")
            item = self.record(data[pos:pos + length])
            pos += length
            if item["name"] in ("\x00", "\x01"):
                continue
            item["path"] = parent + "/" + item.pop("name")
            item["offset"] = item["extent"] * self.sector
            item["within_image"] = item["offset"] + item["size"] <= self.size
            self.entries.append(item)
            if item["directory"] and item["within_image"]:
                self.walk(item, item["path"])

    def get(self, path):
        entry = next(e for e in self.entries if e["path"].upper() == path.upper())
        return self.read(entry["offset"], entry["size"])


def inspect(path):
    iso = Iso(path)
    digest = hashlib.sha256()
    iso.file.seek(0)
    while chunk := iso.file.read(4 * 1024 * 1024):
        digest.update(chunk)
    result = dict(input=str(Path(path).resolve()), size=iso.size, sha256=digest.hexdigest(),
                  container="ISO9660", block_size=iso.block_size,
                  declared_volume_bytes=struct.unpack_from("<I", iso.pvd, 80)[0] * iso.sector,
                  volume_id=iso.pvd[40:72].decode("ascii", "replace").strip(), entries=iso.entries)
    extensions = Counter()
    modules = []
    metadata = {}
    for e in iso.entries:
        if e["directory"] or not e["within_image"]:
            continue
        p = e["path"]
        extensions[Path(p).suffix.upper()] += 1
        head = iso.read(e["offset"], min(e["size"], 0x200))
        e["magic16"] = head[:16].hex()
        # Hash each file without retaining another copy of the game.
        digest = hashlib.sha256()
        for offset in range(0, e["size"], 4 * 1024 * 1024):
            digest.update(iso.read(e["offset"] + offset, min(4 * 1024 * 1024, e["size"] - offset)))
        e["sha256"] = digest.hexdigest()
        if p.upper().endswith("PARAM.SFO"):
            metadata[p] = psf(iso.get(p))
        if p.upper() == "/UMD_DATA.BIN":
            metadata[p] = iso.get(p).rstrip(b"\0").decode("ascii", "replace")
        if Path(p).suffix.upper() in (".PRX", ".ELF") or p.upper().endswith(("EBOOT.BIN", "BOOT.BIN")) or head[:4] in (b"\x7fELF", b"~PSP", b"~SCE"):
            m = dict(path=p, size=e["size"], sha256=e["sha256"], magic=head[:4].hex())
            if head[:4] == b"~PSP":
                m.update(module_name=head[10:38].split(b"\0", 1)[0].decode("ascii", "replace"),
                         module_version=list(head[8:10]), attributes=hex(struct.unpack_from("<H", head, 4)[0]),
                         compression_attributes=hex(struct.unpack_from("<H", head, 6)[0]),
                         elf_size=struct.unpack_from("<I", head, 0x28)[0],
                         psp_size=struct.unpack_from("<I", head, 0x2c)[0],
                         tag=hex(struct.unpack_from("<I", head, 0xd0)[0]))
            elif head[:4] == b"\x7fELF":
                m["elf"] = elf(iso.get(p))
            elif head and not any(head):
                m["zero_header"] = True
            modules.append(m)
    result.update(metadata=metadata, modules=modules, extensions=dict(extensions),
                  files_outside_image=[e["path"] for e in iso.entries if not e["within_image"]])
    iso.file.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = inspect(args.iso)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {k: data[k] for k in ("size", "sha256", "container", "declared_volume_bytes", "metadata", "files_outside_image")}
    summary["files_and_directories"] = len(data["entries"])
    summary["modules"] = [{k: v for k, v in m.items() if k != "elf"} for m in data["modules"]]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
