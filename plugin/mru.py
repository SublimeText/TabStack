from __future__ import annotations

import sublime

from .captions import caption_for_sheet_identities
from .constants import TAB_HISTORY_LIMIT
from .models import Entry, GroupSelectionState, SheetIdentity, SheetSelectionHistory
from .sheets import identities_have_dirty_sheet, sheet_identity


def collect_entries(window: sublime.Window, history: SheetSelectionHistory) -> list[Entry]:
    entries: list[Entry] = []
    active_group = window.active_group()
    seen_identities: set[tuple[str | None, int, str | None, str | None]] = set()

    group_state_stack = history["groups"].get(str(active_group))
    if group_state_stack:
        for group_state in group_state_stack:
            identities = group_state["selected_sheets"]
            entries.append(
                Entry(
                    selection=group_state,
                    caption=caption_for_sheet_identities(identities, window),
                    dirty=identities_have_dirty_sheet(identities, window, active_group),
                )
            )
            seen_identities.update(_selection_identity_keys(group_state))

    for sheet in _non_transient_sheets_in_group(window, active_group):
        if len(entries) >= TAB_HISTORY_LIMIT:
            break
        identity = _identity_key(sheet_identity(sheet, window))
        if identity in seen_identities:
            continue

        entries.append(_entry_for_sheet(sheet, window, active_group))
        seen_identities.add(identity)

    return entries


def _entry_for_sheet(sheet: sublime.Sheet, window: sublime.Window, group: int) -> Entry:
    identity = sheet_identity(sheet, window)
    return Entry(
        selection={
            "active_sheet_index": 0,
            "selected_sheets": [identity],
        },
        caption=caption_for_sheet_identities([identity], window),
        dirty=identities_have_dirty_sheet([identity], window, group),
    )


def _non_transient_sheets_in_group(
    window: sublime.Window,
    group: int,
) -> list[sublime.Sheet]:
    return [sheet for sheet in window.sheets_in_group(group) if not sheet.is_transient()]


def _selection_identity_keys(
    selection: GroupSelectionState,
) -> set[tuple[str | None, int, str | None, str | None]]:
    return {_identity_key(identity) for identity in selection["selected_sheets"]}


def _identity_key(
    identity: SheetIdentity,
) -> tuple[str | None, int, str | None, str | None]:
    return (
        identity["name"],
        identity["occurrence"],
        identity["kind"],
        identity["path"],
    )
