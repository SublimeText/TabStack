"""Serializable data shapes shared across the package.

They live in their own module so the modules operating on them
(`sheets`, `state`, `history`, `mru`) do not need to import each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class SheetIdentity(TypedDict):
    name: str | None
    """The sheet name is `None` on ST builds <4205
    because the required API method does not exist there."""
    occurrence: int
    kind: str | None
    path: str | None


class GroupSelectionState(TypedDict):
    active_sheet_index: int | None
    selected_sheets: list[SheetIdentity]


class SheetSelectionHistory(TypedDict):
    # Only strings may be used as keys in ST settings.
    groups: dict[str, list[GroupSelectionState]]


@dataclass
class Entry:
    selection: GroupSelectionState
    caption: list[str]
    dirty: bool = False
