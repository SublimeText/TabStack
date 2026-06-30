from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, TypedDict

if TYPE_CHECKING:
    from .state import GroupSelectionState


class SheetIdentity(TypedDict):
    name: Optional[str]
    """The sheet name is `None` on ST builds <4205
    because the required API method does not exist there."""
    occurrence: int
    kind: Optional[str]
    path: Optional[str]


def active_sheet_identity(window) -> Optional[SheetIdentity]:
    sheet = window.active_sheet()
    if sheet is None:
        return None
    return sheet_identity(sheet, window)


def find_sheet_by_identity_and_group(window, identity: SheetIdentity, group: int):
    matching = [
        sheet
        for sheet in window.sheets_in_group(group)
        if sheet_name(sheet) == identity["name"]
        and type(sheet).__name__ == identity["kind"]
        and sheet.file_name() == identity["path"]
    ]
    for sheet in matching:
        if sheet_occurrence(sheet, window) == identity["occurrence"]:
            return sheet
    return None


def sheet_identity(sheet, window) -> SheetIdentity:
    return {
        "name": sheet_name(sheet),
        "occurrence": sheet_occurrence(sheet, window),
        "kind": type(sheet).__name__,
        "path": sheet.file_name(),
    }


def sheet_occurrence(sheet, window) -> int:
    group = sheet.group()
    if group is None:
        return 0
    name = sheet_name(sheet)
    kind = type(sheet).__name__
    path = sheet.file_name()

    matching_sheet_ids = [
        candidate.id()
        for candidate in window.sheets_in_group(group)
        if sheet_name(candidate) == name
        and type(candidate).__name__ == kind
        and candidate.file_name() == path
    ]
    try:
        return matching_sheet_ids.index(sheet.id())
    except ValueError:
        return 0


def sheet_title(sheet) -> str:
    file_name = sheet.file_name()
    if file_name:
        return Path(file_name).name
    return "Untitled"


def sheet_name(sheet) -> Optional[str]:
    get_name = getattr(sheet, "name", None)
    return get_name() if get_name else None


def find_live_sheets(window, identities: list[SheetIdentity], group: int) -> list[object]:
    return [
        live_sheet
        for identity in identities
        if (live_sheet := find_sheet_by_identity_and_group(window, identity, group)) is not None
    ]


def apply_group_selection(window, selection: GroupSelectionState, group: int) -> bool:
    sheets_to_select = find_live_sheets(window, selection["selected_sheets"], group)
    if not sheets_to_select:
        return False

    active_sheet_index = selection["active_sheet_index"]
    if active_sheet_index is None or not 0 <= active_sheet_index < len(sheets_to_select):
        active_sheet_index = 0

    window.select_sheets(sheets_to_select)
    window.focus_sheet(sheets_to_select[active_sheet_index])
    return True
