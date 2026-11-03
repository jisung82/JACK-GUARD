"""Use the same process handle for authorization and termination (fail closed)."""

import ctypes as c
import os
from ctypes import wintypes as w


class TOKEN_USER(c.Structure):
    _fields_ = [("sid", c.c_void_p), ("attributes", w.DWORD)]


def libraries():
    kernel = c.WinDLL("kernel32", use_last_error=True)
    adv = c.WinDLL("advapi32", use_last_error=True)
    signatures = [
        (kernel.OpenProcess, [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        (kernel.GetCurrentProcess, [], w.HANDLE),
        (kernel.CloseHandle, [w.HANDLE], w.BOOL),
        (
            kernel.QueryFullProcessImageNameW,
            [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)],
            w.BOOL,
        ),
        (kernel.IsProcessCritical, [w.HANDLE, c.POINTER(w.BOOL)], w.BOOL),
        (kernel.TerminateProcess, [w.HANDLE, w.UINT], w.BOOL),
        (adv.OpenProcessToken, [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL),
        (
            adv.GetTokenInformation,
            [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)],
            w.BOOL,
        ),
        (adv.EqualSid, [c.c_void_p, c.c_void_p], w.BOOL),
        (adv.ConvertSidToStringSidW, [c.c_void_p, c.POINTER(w.LPWSTR)], w.BOOL),
        (kernel.LocalFree, [c.c_void_p], c.c_void_p),
    ]
    for function, args, result in signatures:
        function.argtypes, function.restype = args, result
    return kernel, adv


def token_info(adv, token, kind):
    needed = w.DWORD()
    adv.GetTokenInformation(token, kind, None, 0, c.byref(needed))
    buffer = c.create_string_buffer(needed.value)
    if not adv.GetTokenInformation(token, kind, buffer, needed, c.byref(needed)):
        raise c.WinError(c.get_last_error())
    return buffer


def open_token(adv, process):
    token = w.HANDLE()
    if not adv.OpenProcessToken(process, 8, c.byref(token)):
        raise c.WinError(c.get_last_error())
    return token


def current_sid():
    kernel, adv = libraries()
    token = open_token(adv, kernel.GetCurrentProcess())
    try:
        info = token_info(adv, token, 1)
        sid = c.cast(info, c.POINTER(TOKEN_USER)).contents.sid
        result = w.LPWSTR()
        if not adv.ConvertSidToStringSidW(sid, c.byref(result)):
            raise c.WinError(c.get_last_error())
        try:
            return result.value
        finally:
            kernel.LocalFree(c.cast(result, c.c_void_p))
    finally:
        kernel.CloseHandle(token)


def terminate_owned(pid: int, expected_path: str):
    kernel, adv = libraries()
    process = kernel.OpenProcess(0x1000 | 0x1, False, pid)
    if not process:
        raise PermissionError("프로세스 접근 거부")
    target = own = None
    try:
        path, size = c.create_unicode_buffer(32768), w.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(process, 0, path, c.byref(size)):
            raise PermissionError("실행파일 확인 실패")
        if os.path.normcase(path.value) != os.path.normcase(expected_path):
            raise PermissionError("프로세스 실행파일 변경 감지")
        critical = w.BOOL()
        if not kernel.IsProcessCritical(process, c.byref(critical)) or critical.value:
            raise PermissionError("필수 프로세스 또는 상태 확인 실패")
        target = open_token(adv, process)
        own = open_token(adv, kernel.GetCurrentProcess())
        ti, oi = token_info(adv, target, 1), token_info(adv, own, 1)
        if not adv.EqualSid(
            c.cast(ti, c.POINTER(TOKEN_USER)).contents.sid,
            c.cast(oi, c.POINTER(TOKEN_USER)).contents.sid,
        ):
            raise PermissionError("다른 사용자의 프로세스")
        if token_info(adv, target, 12).raw != token_info(adv, own, 12).raw:
            raise PermissionError("다른 세션의 프로세스")
        if not kernel.TerminateProcess(process, 1):
            raise c.WinError(c.get_last_error())
    finally:
        if target:
            kernel.CloseHandle(target)
        if own:
            kernel.CloseHandle(own)
        kernel.CloseHandle(process)
