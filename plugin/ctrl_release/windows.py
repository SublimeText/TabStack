from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from typing import Any, Optional

from .._compat import sublime
from ._availability import set_unavailable

_VK_CONTROL = 0x11
_USER32: Optional[Any] = None


class CtrlReleasePoller(threading.Thread):
    def __init__(self, on_release: Callable[[], None], interval_ms: int) -> None:
        super().__init__(daemon=True)
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._user32: Any = _get_user32()
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.is_alive():
            return
        self._stop_event.clear()
        super().start()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(self._interval_ms / 1000):
            if self._user32 is None or not self._ctrl_down():
                self._fire_release()
                break

    def _fire_release(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        return bool(self._user32.GetAsyncKeyState(_VK_CONTROL) & 0x8000)

    def _open_user32(self) -> Optional[Any]:
        return _get_user32()


def probe() -> bool:
    return _get_user32() is not None


def _get_user32() -> Optional[Any]:
    global _USER32
    if _USER32 is not None:
        return _USER32

    try:
        user32 = ctypes.CDLL("user32.dll")
    except (AttributeError, OSError) as exc:
        print(f"TabStack: failed to open user32.dll: {exc}")
        set_unavailable()
        return None

    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    _USER32 = user32
    return user32


def plugin_unloaded() -> None:
    global _USER32
    _USER32 = None
