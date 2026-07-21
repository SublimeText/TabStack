from __future__ import annotations

import ctypes
import ctypes.util
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from .._compat import sublime
from ._availability import set_unavailable

_XK_Control_L = 0xFFE3
_XK_Control_R = 0xFFE4
_X11: Optional[Any] = None


@dataclass
class _X11State:
    display: int
    keycode_left: int
    keycode_right: int
    xclose_display: Callable[[int], int]
    xquery_keymap: Callable[[int, Any], int]


class CtrlReleasePoller(threading.Thread):
    def __init__(self, on_release, interval_ms):
        super().__init__(daemon=True)
        self._on_release = on_release
        self._interval_ms = interval_ms
        self._state = self._open_x11_state()
        self._stop_event = threading.Event()
        # libX11 is not thread-safe; serialize all access to the shared Display
        # between the poller thread and the main thread (is_ctrl_down).
        self._display_lock = threading.Lock()

    def start(self) -> None:
        if self.is_alive():
            return
        self._stop_event.clear()
        super().start()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            while not self._stop_event.wait(self._interval_ms / 1000):
                if self._state is None or not self._ctrl_down():
                    self._fire_release()
                    break
        finally:
            self._close_state()

    def _close_state(self) -> None:
        with self._display_lock:
            if self._state is not None:
                self._state.xclose_display(self._state.display)
                self._state = None

    def _fire_release(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        sublime.set_timeout(self._on_release)

    def _ctrl_down(self) -> bool:
        keymap = (ctypes.c_ubyte * 32)()
        with self._display_lock:
            state = self._state
            if state is None:
                return False
            state.xquery_keymap(state.display, keymap)
            keycode_left = state.keycode_left
            keycode_right = state.keycode_right
        return _keycode_is_down(keymap, keycode_left) or _keycode_is_down(
            keymap,
            keycode_right,
        )

    def is_ctrl_down(self) -> bool:
        return self._ctrl_down()

    def _open_x11_state(self) -> Optional[_X11State]:
        display_name = os.environ.get("DISPLAY")
        if not display_name:
            return None

        x11 = _get_x11()
        if x11 is None:
            return None

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


def probe() -> bool:
    return _get_x11() is not None


def _keycode_is_down(keymap, keycode: int) -> bool:
    if not keycode:
        return False
    byte_index = keycode // 8
    bit = keycode % 8
    return bool(keymap[byte_index] & (1 << bit))


def _get_x11() -> Optional[Any]:
    global _X11
    if _X11 is not None:
        return _X11

    lib_name = ctypes.util.find_library("X11") or "libX11.so.6"

    try:
        x11 = ctypes.CDLL(lib_name)
    except OSError as exc:
        print(f"TabStack: failed to open {lib_name}: {exc}")
        set_unavailable()
        return None

    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    x11.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte)]
    x11.XQueryKeymap.restype = ctypes.c_int
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    _X11 = x11
    return x11


def plugin_unloaded() -> None:
    global _X11
    _X11 = None
