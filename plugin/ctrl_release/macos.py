from __future__ import annotations

import ctypes
import ctypes.util
import threading
from collections.abc import Callable
from typing import cast, final

import sublime

from ._availability import set_unavailable

_CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE = 0
_K_VK_CONTROL = 59
_K_VK_RIGHT_CONTROL = 62
_key_state: Callable[[int, int], bool] | None = None


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
        return key_state(
            _CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE,
            _K_VK_CONTROL,
        ) or key_state(
            _CG_EVENT_SOURCE_STATE_COMBINED_SESSION_STATE,
            _K_VK_RIGHT_CONTROL,
        )

    def is_ctrl_down(self) -> bool:
        return self._ctrl_down()


def probe() -> bool:
    return _load_key_state() is not None


def _load_key_state() -> Callable[[int, int], bool] | None:
    global _key_state
    if _key_state is not None:
        return _key_state

    lib_name = ctypes.util.find_library("CoreGraphics")
    if lib_name is None:
        lib_name = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"

    try:
        core_graphics = ctypes.CDLL(lib_name)
    except OSError as exc:
        print(f"TabStack: failed to open {lib_name}: {exc}")
        set_unavailable()
        return None

    key_state = core_graphics.CGEventSourceKeyState
    key_state.argtypes = [ctypes.c_long, ctypes.c_uint32]
    key_state.restype = ctypes.c_bool
    _key_state = cast("Callable[[int, int], bool]", key_state)
    return _key_state


def plugin_unloaded() -> None:
    global _key_state
    _key_state = None
