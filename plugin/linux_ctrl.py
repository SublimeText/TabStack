from __future__ import annotations

import ctypes
import ctypes.util
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ._compat import sublime

_XK_Control_L = 0xFFE3
_XK_Control_R = 0xFFE4


@dataclass(slots=True)
class _X11State:
    display: int
    keycode_left: int
    keycode_right: int
    xclose_display: Callable[[int], int]
    xquery_keymap: Callable[[int, Any], int]


class CtrlReleasePoller:
    def __init__(self, on_release, interval_ms: int = 100):
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._active = False
        self._state = self._open_x11_state()

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._schedule()

    def stop(self) -> None:
        self._active = False
        if self._state is not None:
            self._state.xclose_display(self._state.display)
            self._state = None

    def _schedule(self) -> None:
        if not self._active:
            return
        sublime.set_timeout_async(self._poll, self._interval_ms)

    def _poll(self) -> None:
        if not self._active:
            return
        if self._state is None:
            self._fire_release()
            return
        if not self._ctrl_down():
            self._fire_release()
            return
        self._schedule()

    def _fire_release(self) -> None:
        if not self._active:
            return
        self._active = False
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        state = self._state
        if state is None:
            return False
        keymap = (ctypes.c_ubyte * 32)()
        state.xquery_keymap(state.display, keymap)
        return _keycode_is_down(keymap, state.keycode_left) or _keycode_is_down(
            keymap,
            state.keycode_right,
        )

    def _open_x11_state(self) -> _X11State | None:
        display_name = os.environ.get("DISPLAY")
        if not display_name:
            return None

        lib_name = ctypes.util.find_library("X11") or "libX11.so.6"
        x11 = ctypes.CDLL(lib_name)

        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte)]
        x11.XQueryKeymap.restype = ctypes.c_int
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_ubyte

        display = x11.XOpenDisplay(None)
        if not display:
            return None

        return _X11State(
            display=display,
            keycode_left=int(x11.XKeysymToKeycode(display, _XK_Control_L)),
            keycode_right=int(x11.XKeysymToKeycode(display, _XK_Control_R)),
            xclose_display=x11.XCloseDisplay,
            xquery_keymap=x11.XQueryKeymap,
        )


def _keycode_is_down(keymap, keycode: int) -> bool:
    if not keycode:
        return False
    byte_index = keycode // 8
    bit = keycode % 8
    return bool(keymap[byte_index] & (1 << bit))
