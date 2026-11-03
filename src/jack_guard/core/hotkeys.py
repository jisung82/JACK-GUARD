import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

MODIFIERS = {"Ctrl": 2, "Alt": 1, "Shift": 4, "Win": 8}


def parse_hotkey(text):
    if not isinstance(text, str):
        raise ValueError("단축키 형식 오류")
    pieces = text.split("+")
    if len(pieces) < 2 or len(set(pieces[:-1])) != len(pieces[:-1]):
        raise ValueError("예: Ctrl+Alt+L")
    mods = 0
    for part in pieces[:-1]:
        if part not in MODIFIERS:
            raise ValueError("Ctrl / Alt / Shift / Win을 사용하세요.")
        mods |= MODIFIERS[part]
    key = pieces[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x6F + int(key[1:])
    else:
        raise ValueError("단축키는 영문·숫자 또는 F1~F24 키를 사용하세요.")
    return mods | 0x4000, vk


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, callbacks, api=None):
        super().__init__()
        self.api = api or ctypes.WinDLL("user32", use_last_error=True)
        self.callbacks = callbacks
        self.registered = []

    def register(self, texts):
        parsed = [parse_hotkey(t) for t in texts]
        if len(set(parsed)) != len(parsed):
            raise ValueError("단축키 중복")
        self.close()
        for identifier, (mods, key) in enumerate(parsed, 1):
            ctypes.set_last_error(0)
            if not self.api.RegisterHotKey(None, identifier, mods, key):
                error = ctypes.get_last_error()
                self.close()
                if error == 1409:
                    detail = "단축키 충돌"
                elif error == 5:
                    detail = "단축키 등록 접근 거부"
                else:
                    detail = "단축키 등록 실패"
                raise OSError(f"{detail}: {texts[identifier - 1]} (Windows 오류 {error})")
            self.registered.append(identifier)

    def close(self):
        for identifier in self.registered:
            self.api.UnregisterHotKey(None, identifier)
        self.registered.clear()

    def nativeEventFilter(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == 0x0312 and msg.wParam in self.registered:
            self.callbacks[msg.wParam - 1]()
            return True, 0
        return False, 0
