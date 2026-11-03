import ctypes
import sys


def lock_workstation(api=None):
    if api is None:
        if sys.platform != "win32":
            raise OSError("Windows에서만 사용할 수 있습니다.")
        api = ctypes.WinDLL("user32", use_last_error=True).LockWorkStation
        api.argtypes = []
        api.restype = ctypes.c_int
    if not api():
        raise OSError("Windows 잠금 요청에 실패했습니다.")
