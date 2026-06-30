from __future__ import annotations

from collections.abc import Callable
from typing import Optional

_AVAILABLE: Optional[bool] = None


def set_unavailable() -> None:
    global _AVAILABLE
    _AVAILABLE = False


def is_available(probe: Callable[[], bool]) -> bool:
    global _AVAILABLE
    if _AVAILABLE is None:
        _AVAILABLE = probe()
    return _AVAILABLE


def reset() -> None:
    global _AVAILABLE
    _AVAILABLE = None
