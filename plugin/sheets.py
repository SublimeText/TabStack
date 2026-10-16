from __future__ import annotations

from typing import Callable, Optional, cast

import sublime

from .models import GroupSelectionState, SheetIdentity


def active_sheet_identity(window: sublime.Window) -> SheetIdentity | None:
    sheet = window.active_sheet()
    if sheet is None:
        return None
    return sheet_identity(sheet, window)


def find_sheet_by_identity_and_group(
    window: sublime.Window,
    identity: SheetIdentity,
    group: int,
) -> sublime.Sheet | None:
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


def sheet_identity(sheet: sublime.Sheet, window: sublime.Window) -> SheetIdentity:
    return {
        "name": sheet_name(sheet),
        "occurrence": sheet_occurrence(sheet, window),
        "kind": type(sheet).__name__,
        "path": sheet.file_name(),
    }


def sheet_occurrence(sheet: sublime.Sheet, window: sublime.Window) -> int:
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


def sheet_name(sheet: sublime.Sheet) -> str | None:
    # `Sheet.name` only exists on ST builds >=4205.
    get_name = cast(Optional[Callable[[], str]], getattr(sheet, "name", None))
    return get_name() if get_name else None


def sheet_is_dirty(sheet: sublime.Sheet) -> bool:
    view = sheet.view()
    return view is not None and view.is_dirty()


def identities_have_dirty_sheet(
    identities: list[SheetIdentity],
    window: sublime.Window,
    group: int,
) -> bool:
    return any(
        (sheet := find_sheet_by_identity_and_group(window, identity, group)) is not None
        and sheet_is_dirty(sheet)
        for identity in identities
    )


def find_live_sheets(
    window: sublime.Window,
    identities: list[SheetIdentity],
    group: int,
) -> list[sublime.Sheet]:
    return [
        live_sheet
        for identity in identities
        if (live_sheet := find_sheet_by_identity_and_group(window, identity, group)) is not None
    ]


def apply_group_selection(
    window: sublime.Window,
    selection: GroupSelectionState,
    group: int,
) -> bool:
    sheets_to_select = find_live_sheets(window, selection["selected_sheets"], group)
    if not sheets_to_select:
        return False

    active_sheet_index = selection["active_sheet_index"]
    if active_sheet_index is None or not 0 <= active_sheet_index < len(sheets_to_select):
        active_sheet_index = 0

    window.select_sheets(sheets_to_select)
    window.focus_sheet(sheets_to_select[active_sheet_index])
    return True
