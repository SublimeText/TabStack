from __future__ import annotations

import ctypes
import ctypes.util
import threading
from collections.abc import Callable
from typing import Any, Optional

from .._compat import sublime
from ._availability import set_unavailable

_CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE = 0
_K_VK_CONTROL = 59
_K_VK_RIGHT_CONTROL = 62
_CORE_GRAPHICS: Optional[Any] = None


class CtrlReleasePoller(threading.Thread):
    def __init__(self, on_release: Callable[[], None], interval_ms: int) -> None:
        super().__init__(daemon=True)
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._core_graphics = _get_core_graphics()
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
            if self._core_graphics is None or not self._ctrl_down():
                self._fire_release()
                break

    def _fire_release(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        core_graphics = self._core_graphics
        if core_graphics is None:
            return False
        return bool(
            core_graphics.CGEventSourceKeyState(
                _CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE,
                _K_VK_CONTROL,
            )
            or core_graphics.CGEventSourceKeyState(
                _CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE,
                _K_VK_RIGHT_CONTROL,
            )
        )

    def _open_core_graphics(self) -> Optional[Any]:
        return _get_core_graphics()


def probe() -> bool:
    return _get_core_graphics() is not None


def _get_core_graphics() -> Optional[Any]:
    global _CORE_GRAPHICS
    if _CORE_GRAPHICS is not None:
        return _CORE_GRAPHICS

    lib_name = ctypes.util.find_library("CoreGraphics")
    if lib_name is None:
        lib_name = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"

    try:
        core_graphics = ctypes.CDLL(lib_name)
    except OSError as exc:
        print(f"TabStack: failed to open {lib_name}: {exc}")
        set_unavailable()
        return None

    core_graphics.CGEventSourceKeyState.argtypes = [ctypes.c_long, ctypes.c_uint32]
    core_graphics.CGEventSourceKeyState.restype = ctypes.c_bool
    _CORE_GRAPHICS = core_graphics
    return core_graphics


def plugin_unloaded() -> None:
    global _CORE_GRAPHICS
    _CORE_GRAPHICS = None
