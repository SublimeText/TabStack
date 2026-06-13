from __future__ import annotations

import sys

from ._availability import is_available as _is_available
from ._availability import reset as _reset_availability

if sys.platform == "darwin":
    from .macos import CtrlReleasePoller, probe
    from .macos import plugin_unloaded as _platform_plugin_unloaded
elif sys.platform == "win32":
    from .windows import CtrlReleasePoller, probe
    from .windows import plugin_unloaded as _platform_plugin_unloaded
else:
    from .linux import CtrlReleasePoller, probe
    from .linux import plugin_unloaded as _platform_plugin_unloaded


def is_available() -> bool:
    return _is_available(probe)


def plugin_unloaded() -> None:
    _platform_plugin_unloaded()
    _reset_availability()


__all__ = [
    "CtrlReleasePoller",
    "is_available",
    "probe",
    "plugin_unloaded",
]
