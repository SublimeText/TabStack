from __future__ import annotations

import sys

if sys.platform == "darwin":
    from .macos import CtrlReleasePoller, plugin_unloaded
elif sys.platform == "win32":
    from .windows import CtrlReleasePoller, plugin_unloaded
else:
    from .linux import CtrlReleasePoller, plugin_unloaded

__all__ = [
    "CtrlReleasePoller",
    "plugin_unloaded",
]
