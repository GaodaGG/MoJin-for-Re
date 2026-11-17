"""Visible, no-argument launch from a different cwd and without a toolchain PATH.

Uses private saves. The user closes the window, or --close-after requests it.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument('--deny-iso', action='store_true', help='Make the original ISO unavailable throughout this no-argument test without modifying it')
    parser.add_argument("--close-after", type=int, help="Request normal WM_CLOSE on this test process's visible game window after N seconds")
    args = parser.parse_args()
    if args.close_after is not None and not 10 <= args.close_after <= 120:
        parser.error("--close-after must be 10..120 seconds")
    package = args.package.resolve()
    if not any(package.is_relative_to(ROOT / base) for base in ("development/releases","development/tests/standalone")):
        parser.error("Use a private staged package, not the normal play folder")
    exe = package / "MoJin.exe"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SR_", "PSP_"))}
    env["PATH"] = os.environ["SystemRoot"] + "\\System32"
    env["SR_HEADLESS"] = "1"  # Must be cleared by native no-argument startup.
    env["SR_NOVBPACE"] = "1"
    start = time.monotonic()
    iso_record, release_iso = None, None
    if args.deny_iso:
        from iso_unavailable import hold_iso_unavailable
        iso_record, release_iso = hold_iso_unavailable()
    process = subprocess.Popen([str(exe)], cwd=os.environ["SystemRoot"], env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    record = dict(pid=process.pid, command=[str(exe)], argc=1,
                  launch_cwd=os.environ["SystemRoot"], path_has_toolchain=False,
                  executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  started_utc=datetime.now(timezone.utc).isoformat(), private_saves=str(package / "saves"))
    if iso_record: record['iso_unavailable'] = iso_record
    target = ROOT / f"development/evidence/standalone-{package.name}-test.json"
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2), flush=True)
    if args.close_after is not None:
        while process.poll() is None and time.monotonic()-start < args.close_after:
            time.sleep(0.2)
        record["close_requested"] = False
        if process.poll() is None:
            user32 = ctypes.WinDLL("user32",use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            user32.IsWindowVisible.argtypes=[wintypes.HWND]
            user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
            user32.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
            handles=[]
            owned=[]
            @callback_type
            def visit(hwnd,param):
                pid=wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                if pid.value == process.pid and user32.IsWindowVisible(hwnd):
                    title=ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd,title,len(title))
                    owned.append(title.value)
                    if title.value == '魔法禁书目录' or title.value.startswith('魔法禁书目录 -'):
                        handles.append(hwnd)
                return True
            user32.EnumWindows(visit,0)
            if len(handles)==1:
                record["close_requested"]=bool(user32.PostMessageW(handles[0],0x0010,0,0))
            record["matching_owned_windows"]=len(handles)
            record["visible_owned_window_titles"]=owned
        try:
            record["exit_code"] = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            record["timed_out_after_close"]=True
            process.terminate()  # only the handle created above, never by image name
            record["exit_code"]=process.wait(timeout=10)
    else:
        record["exit_code"] = process.wait()
    record["elapsed_seconds"] = time.monotonic() - start
    if release_iso: release_iso()
    record["logs"] = [str(p.relative_to(ROOT)) for p in sorted((package/'logs').glob(f'*-{process.pid}.log'))]
    record["savedata"] = {p.relative_to(package).as_posix(): dict(bytes=p.stat().st_size,
                         sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                         for p in (package / "saves").rglob("*") if p.is_file()}
    (package/'standalone-test.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2), flush=True)


if __name__ == "__main__":
    main()
