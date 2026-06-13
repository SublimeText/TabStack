from __future__ import annotations

import sys

if sys.platform == "darwin":
    from .macos import CtrlReleasePoller
elif sys.platform == "win32":
    from .windows import CtrlReleasePoller
else:
    from .linux import CtrlReleasePoller

__all__ = [
    "CtrlReleasePoller",
]
