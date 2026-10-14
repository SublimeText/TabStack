from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from typing import cast, final

import sublime

from ._availability import set_unavailable

_VK_CONTROL = 0x11
_get_async_key_state: Callable[[int], int] | None = None


@final
class CtrlReleasePoller(threading.Thread):
    def __init__(self, on_release: Callable[[], None], interval_ms: int) -> None:
        super().__init__(daemon=True)
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._key_state = _load_key_state()
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.is_alive():
            return
        self._stop_event.clear()
        super().start()

    def run(self) -> None:
        while not self._stop_event.wait(self._interval_ms / 1000):
            if self._key_state is None or not self._ctrl_down():
                self._fire_release()
                break

    def stop(self) -> None:
        self._stop_event.set()

    def _fire_release(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        key_state = self._key_state
        if key_state is None:
            return False
        return bool(key_state(_VK_CONTROL) & 0x8000)

    def is_ctrl_down(self) -> bool:
        return self._ctrl_down()


def probe() -> bool:
    return _load_key_state() is not None


def _load_key_state() -> Callable[[int], int] | None:
    global _get_async_key_state
    if _get_async_key_state is not None:
        return _get_async_key_state

    try:
        user32 = ctypes.CDLL("user32.dll")
    except (AttributeError, OSError) as exc:
        print(f"TabStack: failed to open user32.dll: {exc}")
        set_unavailable()
        return None

    get_async_key_state = user32.GetAsyncKeyState
    get_async_key_state.argtypes = [ctypes.c_int]
    get_async_key_state.restype = ctypes.c_short
    _get_async_key_state = cast("Callable[[int], int]", get_async_key_state)
    return _get_async_key_state


def plugin_unloaded() -> None:
    global _get_async_key_state
    _get_async_key_state = None
