from __future__ import annotations

from collections.abc import Callable

_available: bool | None = None


def set_unavailable() -> None:
    global _available
    _available = False


def is_available(probe: Callable[[], bool]) -> bool:
    global _available
    if _available is None:
        _available = probe()
    return _available


def reset() -> None:
    global _available
    _available = None
