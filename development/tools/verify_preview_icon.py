"""Read PE resources as data and compare all embedded icon images to game.ico."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import struct

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--exe', type=Path, default=root / 'play/MoJin.exe')
parser.add_argument('--record', type=Path, default=root / 'development/evidence/preview-icon-test.json')
args = parser.parse_args()
exe = args.exe.resolve()
record_path = args.record.resolve()
if not exe.is_relative_to(root) or not record_path.is_relative_to(root / 'development/evidence'):
    parser.error('Use a project executable and development evidence path')
icon = (root / "development/assets/game.ico").read_bytes()
kernel = c.WinDLL("kernel32", use_last_error=True)
kernel.LoadLibraryExW.argtypes = [w.LPCWSTR, c.c_void_p, w.DWORD]
kernel.LoadLibraryExW.restype = c.c_void_p
kernel.FindResourceW.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
kernel.FindResourceW.restype = c.c_void_p
kernel.SizeofResource.argtypes = [c.c_void_p, c.c_void_p]
kernel.SizeofResource.restype = w.DWORD
kernel.LoadResource.argtypes = [c.c_void_p, c.c_void_p]
kernel.LoadResource.restype = c.c_void_p
kernel.LockResource.argtypes = [c.c_void_p]
kernel.LockResource.restype = c.c_void_p
kernel.FreeLibrary.argtypes = [c.c_void_p]
module = kernel.LoadLibraryExW(str(exe), None, 0x02 | 0x20)
assert module, c.get_last_error()


def resource(kind, number):
    r = kernel.FindResourceW(module, c.c_void_p(number), c.c_void_p(kind))
    assert r, (kind, number)
    size = kernel.SizeofResource(module, r)
    return c.string_at(kernel.LockResource(kernel.LoadResource(module, r)), size)


try:
    group = resource(14, 1)
    count = struct.unpack_from("<H", group, 4)[0]
    assert count == struct.unpack_from("<H", icon, 4)[0]
    for i in range(count):
        size, offset = struct.unpack_from("<II", icon, 6 + i * 16 + 8)
        entry = struct.unpack_from("<BBBBHHIH", group, 6 + i * 14)
        assert resource(3, entry[-1]) == icon[offset:offset + size]
    record = dict(executable=str(exe), executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  icon_groups=1, icon_images_verified=count, exact_image_payloads_match=True)
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
finally:
    kernel.FreeLibrary(module)
