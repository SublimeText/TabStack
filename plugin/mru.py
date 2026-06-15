from __future__ import annotations

from dataclasses import dataclass

from .captions import caption_for_sheet_identities
from .sheets import SheetIdentity, sheet_identity
from .state import GroupSelectionState, SheetSelectionHistory


@dataclass(slots=True)
class Entry:
    selection: GroupSelectionState
    caption: list[str]


def collect_entries(window, history: SheetSelectionHistory) -> list[Entry]:
    entries: list[Entry] = []
    active_group = window.active_group()
    seen_identities: set[tuple[str, int, str | None, str | None]] = set()

    group_state_stack = history["groups"].get(str(active_group))
    if group_state_stack:
        for group_state in group_state_stack:
            entries.append(
                Entry(
                    selection=group_state,
                    caption=caption_for_sheet_identities(group_state["selected_sheets"], window),
                )
            )
            seen_identities.update(_selection_identity_keys(group_state))

    for sheet in _non_transient_sheets_in_group(window, active_group):
        identity = _identity_key(sheet_identity(sheet, window))
        if identity in seen_identities:
            continue

        entries.append(_entry_for_sheet(sheet, window))
        seen_identities.add(identity)

    return entries


def _entry_for_sheet(sheet, window) -> Entry:
    identity = sheet_identity(sheet, window)
    return Entry(
        selection={
            "active_sheet_index": 0,
            "selected_sheets": [identity],
        },
        caption=caption_for_sheet_identities([identity], window),
    )


def _non_transient_sheets_in_group(window, group: int):
    return [sheet for sheet in window.sheets_in_group(group) if not sheet.is_transient()]


def _selection_identity_keys(
    selection: GroupSelectionState,
) -> set[tuple[str, int, str | None, str | None]]:
    return {_identity_key(identity) for identity in selection["selected_sheets"]}


def _identity_key(identity: SheetIdentity) -> tuple[str, int, str | None, str | None]:
    return (
        identity["name"],
        identity["occurrence"],
        identity["kind"],
        identity["path"],
    )
