from __future__ import annotations

import ctypes
import ctypes.util
from collections.abc import Callable
from typing import Any

from .._compat import sublime
from ._availability import set_unavailable

_CGEventTapProxy = ctypes.c_void_p
_CGEventType = ctypes.c_uint32
_CGEventRef = ctypes.c_void_p
_CGEventFlags = ctypes.c_uint64
_CFMachPortRef = ctypes.c_void_p
_CFRunLoopRef = ctypes.c_void_p
_CFRunLoopSourceRef = ctypes.c_void_p
_CFStringRef = ctypes.c_void_p
_CGEventTapCallBack = ctypes.CFUNCTYPE(
    _CGEventRef,
    _CGEventTapProxy,
    _CGEventType,
    _CGEventRef,
    ctypes.c_void_p,
)

_K_CG_HID_EVENT_TAP = 0
_K_CG_HEAD_INSERT_EVENT_TAP = 0
_K_CG_EVENT_TAP_OPTION_LISTEN_ONLY = 1
_K_CG_EVENT_FLAGS_CHANGED = 12
_K_CG_EVENT_FLAG_MASK_CONTROL = 1 << 18

_CORE_GRAPHICS: Any | None = None
_CORE_FOUNDATION: Any | None = None
_RUN_LOOP_DEFAULT_MODE: _CFStringRef | None = None


class CtrlReleasePoller:
    def __init__(self, on_release: Callable[[], None], interval_ms: int) -> None:
        self._on_release = on_release
        self._active = False
        self._callback: Any | None = None
        self._event_tap: _CFMachPortRef | None = None
        self._run_loop_source: _CFRunLoopSourceRef | None = None
        self._run_loop: _CFRunLoopRef | None = None
        self._core_graphics = _get_core_graphics()
        self._core_foundation = _get_core_foundation()

    def start(self) -> None:
        if self._active:
            return

        self._active = True
        core_graphics = self._core_graphics
        core_foundation = self._core_foundation
        if core_graphics is None or core_foundation is None:
            self._deactivate()
            return

        callback = self._make_callback(core_graphics)
        event_tap = core_graphics.CGEventTapCreate(
            _K_CG_HID_EVENT_TAP,
            _K_CG_HEAD_INSERT_EVENT_TAP,
            _K_CG_EVENT_TAP_OPTION_LISTEN_ONLY,
            ctypes.c_uint64(1 << _K_CG_EVENT_FLAGS_CHANGED),
            callback,
            None,
        )
        if not event_tap:
            print("TabStack: failed to create macOS event tap")
            self._deactivate()
            return

        run_loop_source = core_foundation.CFMachPortCreateRunLoopSource(None, event_tap, 0)
        if not run_loop_source:
            print("TabStack: failed to create macOS event tap source")
            core_graphics.CGEventTapEnable(event_tap, False)
            core_foundation.CFMachPortInvalidate(event_tap)
            core_foundation.CFRelease(event_tap)
            self._deactivate()
            return

        run_loop = core_foundation.CFRunLoopGetCurrent()
        mode = _run_loop_default_mode(core_foundation)
        if not run_loop or mode is None:
            print("TabStack: failed to get macOS run loop mode")
            core_foundation.CFRelease(run_loop_source)
            core_graphics.CGEventTapEnable(event_tap, False)
            core_foundation.CFMachPortInvalidate(event_tap)
            core_foundation.CFRelease(event_tap)
            self._deactivate()
            return

        self._callback = callback
        self._event_tap = event_tap
        self._run_loop_source = run_loop_source
        self._run_loop = run_loop

        core_foundation.CFRunLoopAddSource(run_loop, run_loop_source, mode)
        core_graphics.CGEventTapEnable(event_tap, True)

    def stop(self) -> None:
        if not self._active and self._event_tap is None and self._run_loop_source is None:
            return

        self._active = False
        self._remove_tap()

    def _make_callback(self, core_graphics: Any):
        def callback(proxy, event_type, event, refcon):
            if not self._active:
                return event

            if event_type == _K_CG_EVENT_FLAGS_CHANGED:
                flags = core_graphics.CGEventGetFlags(event)
                if not (flags & _K_CG_EVENT_FLAG_MASK_CONTROL):
                    self._fire_release()

            return event

        return _CGEventTapCallBack(callback)

    def _fire_release(self) -> None:
        if not self._active:
            return

        self._active = False
        self._remove_tap()
        sublime.set_timeout(self._on_release)

    def _deactivate(self) -> None:
        self._active = False
        self._callback = None
        self._event_tap = None
        self._run_loop_source = None
        self._run_loop = None

    def _remove_tap(self) -> None:
        core_graphics = self._core_graphics
        core_foundation = self._core_foundation
        event_tap = self._event_tap
        run_loop_source = self._run_loop_source
        run_loop = self._run_loop
        mode = _run_loop_default_mode(core_foundation) if core_foundation is not None else None

        if (
            core_foundation is not None
            and run_loop is not None
            and run_loop_source is not None
            and mode is not None
        ):
            core_foundation.CFRunLoopRemoveSource(run_loop, run_loop_source, mode)

        if core_graphics is not None and event_tap is not None:
            core_graphics.CGEventTapEnable(event_tap, False)

        if core_foundation is not None:
            if event_tap is not None:
                core_foundation.CFMachPortInvalidate(event_tap)
            if run_loop_source is not None:
                core_foundation.CFRelease(run_loop_source)
            if event_tap is not None:
                core_foundation.CFRelease(event_tap)

        self._callback = None
        self._event_tap = None
        self._run_loop_source = None
        self._run_loop = None


def probe() -> bool:
    return _get_core_graphics() is not None and _get_core_foundation() is not None


def _get_core_graphics() -> Any | None:
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

    core_graphics.CGEventTapCreate.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint64,
        _CGEventTapCallBack,
        ctypes.c_void_p,
    ]
    core_graphics.CGEventTapCreate.restype = _CFMachPortRef
    core_graphics.CGEventTapEnable.argtypes = [_CFMachPortRef, ctypes.c_bool]
    core_graphics.CGEventTapEnable.restype = None
    core_graphics.CGEventGetFlags.argtypes = [_CGEventRef]
    core_graphics.CGEventGetFlags.restype = _CGEventFlags
    _CORE_GRAPHICS = core_graphics
    return core_graphics


def _get_core_foundation() -> Any | None:
    global _CORE_FOUNDATION
    if _CORE_FOUNDATION is not None:
        return _CORE_FOUNDATION

    lib_name = ctypes.util.find_library("CoreFoundation")
    if lib_name is None:
        lib_name = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"

    try:
        core_foundation = ctypes.CDLL(lib_name)
    except OSError as exc:
        print(f"TabStack: failed to open {lib_name}: {exc}")
        set_unavailable()
        return None

    core_foundation.CFMachPortCreateRunLoopSource.argtypes = [
        ctypes.c_void_p,
        _CFMachPortRef,
        ctypes.c_long,
    ]
    core_foundation.CFMachPortCreateRunLoopSource.restype = _CFRunLoopSourceRef
    core_foundation.CFMachPortInvalidate.argtypes = [_CFMachPortRef]
    core_foundation.CFMachPortInvalidate.restype = None
    core_foundation.CFRunLoopGetCurrent.argtypes = []
    core_foundation.CFRunLoopGetCurrent.restype = _CFRunLoopRef
    core_foundation.CFRunLoopAddSource.argtypes = [_CFRunLoopRef, _CFRunLoopSourceRef, _CFStringRef]
    core_foundation.CFRunLoopAddSource.restype = None
    core_foundation.CFRunLoopRemoveSource.argtypes = [
        _CFRunLoopRef,
        _CFRunLoopSourceRef,
        _CFStringRef,
    ]
    core_foundation.CFRunLoopRemoveSource.restype = None
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_foundation.CFRelease.restype = None
    _CORE_FOUNDATION = core_foundation
    return core_foundation


def _run_loop_default_mode(core_foundation: Any) -> _CFStringRef | None:
    global _RUN_LOOP_DEFAULT_MODE
    if _RUN_LOOP_DEFAULT_MODE is not None:
        return _RUN_LOOP_DEFAULT_MODE

    try:
        mode = ctypes.c_void_p.in_dll(core_foundation, "kCFRunLoopDefaultMode")
    except ValueError:
        return None

    _RUN_LOOP_DEFAULT_MODE = mode
    return mode


def plugin_unloaded() -> None:
    global _CORE_GRAPHICS, _CORE_FOUNDATION, _RUN_LOOP_DEFAULT_MODE
    _CORE_GRAPHICS = None
    _CORE_FOUNDATION = None
    _RUN_LOOP_DEFAULT_MODE = None
