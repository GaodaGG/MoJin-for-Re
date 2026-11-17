"""Windows allocation accounting, deduplicating file IDs and skipping directory links."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
kernel.CloseHandle.argtypes = [wintypes.HANDLE]


class StandardInfo(ctypes.Structure):
    _fields_ = [("allocation", ctypes.c_longlong), ("end", ctypes.c_longlong),
                ("links", wintypes.DWORD), ("deleted", ctypes.c_ubyte), ("directory", ctypes.c_ubyte)]


def allocation(path):
    handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = StandardInfo()
        if not kernel.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.allocation
    finally:
        kernel.CloseHandle(handle)


def main():
    pending = [ROOT]
    seen = set()
    groups = {}
    skipped = []
    errors = []
    while pending:
        directory = pending.pop()
        for item in os.scandir(directory):
            path = Path(item.path)
            rel = path.relative_to(ROOT)
            if item.is_symlink() or item.is_junction():
                skipped.append(str(rel))
                continue
            if item.is_dir(follow_symlinks=False):
                pending.append(path)
                continue
            try:
                # Windows DirEntry.stat() supplies st_ino=0; os.stat opens the
                # path and obtains the actual file ID needed for deduplication.
                st = path.stat(follow_symlinks=False)
                key = (st.st_dev, st.st_ino)
                group = "/".join(rel.parts[:2]) if rel.parts[0] == "development" else rel.parts[0]
                row = groups.setdefault(group, dict(files=0, logical_bytes=0, allocated_bytes=0, duplicate_file_ids=0))
                if key in seen:
                    row["duplicate_file_ids"] += 1
                    continue
                seen.add(key)
                row["files"] += 1
                row["logical_bytes"] += st.st_size
                row["allocated_bytes"] += allocation(path)
            except OSError as exc:
                errors.append(dict(path=str(rel), error=str(exc)))
    report = dict(method="GetFileInformationByHandleEx(FileStandardInfo).AllocationSize; unique volume/file IDs; no junction traversal",
                  groups=groups, skipped_links=skipped, errors=errors,
                  allocated_bytes=sum(x["allocated_bytes"] for x in groups.values()),
                  logical_bytes=sum(x["logical_bytes"] for x in groups.values()))
    (ROOT / "development/evidence/disk-usage.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("allocated_bytes", "logical_bytes", "errors")}, ensure_ascii=False))
    for name, row in sorted(groups.items()):
        print(f"{name}: {row['allocated_bytes'] / (1024 ** 2):.2f} MiB allocated, {row['files']} files")


if __name__ == "__main__":
    main()
