from __future__ import annotations

import ctypes
from typing import Any

from .._compat import sublime

_VK_CONTROL = 0x11


class CtrlReleasePoller:
    def __init__(self, on_release, interval_ms):
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._active = False
        self._user32: Any = self._open_user32()

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._schedule()

    def stop(self) -> None:
        self._active = False

    def _schedule(self) -> None:
        if not self._active:
            return
        sublime.set_timeout_async(self._poll, self._interval_ms)

    def _poll(self) -> None:
        if not self._active:
            return
        if self._user32 is None or not self._ctrl_down():
            self._fire_release()
            return
        self._schedule()

    def _fire_release(self) -> None:
        if not self._active:
            return
        self._active = False
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        return bool(self._user32.GetAsyncKeyState(_VK_CONTROL) & 0x8000)

    def _open_user32(self) -> Any | None:
        try:
            user32 = ctypes.CDLL("user32.dll")
        except AttributeError, OSError:
            return None

        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        return user32
