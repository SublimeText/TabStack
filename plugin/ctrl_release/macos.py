from __future__ import annotations

import ctypes
import ctypes.util
from collections.abc import Callable
from typing import Any

from .._compat import sublime

_CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE = 0
_K_VK_CONTROL = 59
_K_VK_RIGHT_CONTROL = 62
_CORE_GRAPHICS: Any | None = None


class CtrlReleasePoller:
    def __init__(self, on_release: Callable[[], None], interval_ms: int) -> None:
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._active = False
        self._core_graphics = _get_core_graphics()

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
        if self._core_graphics is None or not self._ctrl_down():
            self._fire_release()
            return
        self._schedule()

    def _fire_release(self) -> None:
        if not self._active:
            return
        self._active = False
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

    def _open_core_graphics(self) -> Any | None:
        return _get_core_graphics()


def _get_core_graphics() -> Any | None:
    global _CORE_GRAPHICS
    if _CORE_GRAPHICS is not None:
        return _CORE_GRAPHICS

    lib_name = ctypes.util.find_library("CoreGraphics")
    if lib_name is None:
        lib_name = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"

    try:
        core_graphics = ctypes.CDLL(lib_name)
    except OSError:
        return None

    core_graphics.CGEventSourceKeyState.argtypes = [ctypes.c_long, ctypes.c_uint32]
    core_graphics.CGEventSourceKeyState.restype = ctypes.c_bool
    _CORE_GRAPHICS = core_graphics
    return core_graphics


def plugin_unloaded() -> None:
    global _CORE_GRAPHICS
    _CORE_GRAPHICS = None
