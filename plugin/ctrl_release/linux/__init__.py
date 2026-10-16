from __future__ import annotations

import os
from collections.abc import Callable

from ...state import CtrlPoller
from .keystate_helper import HelperCtrlReleasePoller, HelperProbe, HelperStatus, get_helper_probe
from .keystate_helper import plugin_unloaded as _helper_plugin_unloaded
from .x11 import X11CtrlReleasePoller, is_x11_available
from .x11 import plugin_unloaded as _x11_plugin_unloaded


def is_native_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) and os.environ.get("GDK_BACKEND") != "x11"


def create_poller(on_release: Callable[[], None], interval_ms: int) -> CtrlPoller:
    helper_probe = _working_helper_probe()
    if helper_probe is not None:
        return HelperCtrlReleasePoller(on_release, interval_ms, helper_probe)
    return X11CtrlReleasePoller(on_release, interval_ms)


def probe() -> bool:
    if _working_helper_probe() is not None:
        return True
    # Under native Wayland, XWayland reports Ctrl as released while Sublime has focus,
    # which would commit every session immediately.
    return not is_native_wayland() and is_x11_available()


def _working_helper_probe() -> HelperProbe | None:
    helper_probe = get_helper_probe()
    if helper_probe is None or helper_probe.status is not HelperStatus.OK:
        return None
    return helper_probe


def plugin_unloaded() -> None:
    _x11_plugin_unloaded()
    _helper_plugin_unloaded()
