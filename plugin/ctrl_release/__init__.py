from __future__ import annotations

import sys
from collections.abc import Callable

from ._availability import is_available as _is_available
from ._availability import reset as _reset_availability

if sys.platform == "darwin":
    from .macos import CtrlReleasePoller as create_poller
    from .macos import plugin_unloaded as _platform_plugin_unloaded
    from .macos import probe

    def _start_platform_probe(on_done: Callable[[], None]) -> None:
        on_done()

    def _watch_platform(on_invalidated: Callable[[], None]) -> None:
        _ = on_invalidated

    def is_native_wayland() -> bool:
        return False

elif sys.platform == "win32":
    from .windows import CtrlReleasePoller as create_poller
    from .windows import plugin_unloaded as _platform_plugin_unloaded
    from .windows import probe

    def _start_platform_probe(on_done: Callable[[], None]) -> None:
        on_done()

    def _watch_platform(on_invalidated: Callable[[], None]) -> None:
        _ = on_invalidated

    def is_native_wayland() -> bool:
        return False

else:
    from .linux import create_poller, is_native_wayland, probe
    from .linux import plugin_unloaded as _platform_plugin_unloaded
    from .linux.keystate_helper import HelperProbe, start_helper_probe
    from .linux.keystate_helper import watch_helper as _watch_platform

    def _start_platform_probe(on_done: Callable[[], None]) -> None:
        def on_helper_probed(_: HelperProbe) -> None:
            on_done()

        start_helper_probe(on_helper_probed)


def is_available() -> bool:
    return _is_available(probe)


def refresh_availability(on_done: Callable[[], None] = lambda: None) -> None:
    """Probe the platform in the background and call `on_done` on the main thread.

    Until then, `is_available` answers without the platform probe's result.
    """

    def on_probed() -> None:
        # Drop the answer given while the probe was running.
        _reset_availability()
        on_done()

    _reset_availability()
    _start_platform_probe(on_probed)


def plugin_loaded() -> None:
    refresh_availability()
    # The probe result only holds for the settings it was made with,
    # and only until the probed helper fails.
    _watch_platform(refresh_availability)


def plugin_unloaded() -> None:
    _platform_plugin_unloaded()
    _reset_availability()


__all__ = [
    "create_poller",
    "is_available",
    "is_native_wayland",
    "probe",
    "plugin_loaded",
    "plugin_unloaded",
    "refresh_availability",
]
