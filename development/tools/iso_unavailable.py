"""Temporarily deny opening the original ISO with a read-only Windows handle.

No rename, ACL change, modification or deletion. The OS releases the lock when
this test process exits even if the probe itself fails.
"""
import atexit
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path


def hold_iso_unavailable():
    path=Path(__file__).resolve().parents[2]/'魔法禁书目录.iso'
    k=c.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
    k.CreateFileW.restype=w.HANDLE
    k.CloseHandle.argtypes=[w.HANDLE]
    invalid=c.c_void_p(-1).value
    h=k.CreateFileW(str(path),0x80000000,0,None,3,0x80,None)
    if h==invalid: raise OSError(c.get_last_error(),'Cannot reserve the read-only ISO test lock')
    alive=[h]
    def release():
        if alive: k.CloseHandle(alive.pop())
    atexit.register(release)
    other=k.CreateFileW(str(path),0x80000000,7,None,3,0x80,None)
    error=c.get_last_error()
    if other!=invalid:
        k.CloseHandle(other); release(); raise AssertionError('ISO was unexpectedly readable')
    assert error==32, error
    return dict(original_path=str(path),read_only_exclusive_handle=True,
                second_open_error=error,original_modified=False),release
