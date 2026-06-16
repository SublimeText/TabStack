from __future__ import annotations

from typing import Any, cast

from ._compat import sublime
from .sheets import SheetIdentity, find_sheet_by_identity_and_group, sheet_identity
from .state import (
    GroupSelectionState,
    SheetSelectionHistory,
    TabStackWindowState,
    get_state,
)

_HISTORY_KEY = "tab_stack.sheet_selection_history"


class SelectionHistoryPoller:
    def __init__(self, state: TabStackWindowState, window, interval_ms: int = 500) -> None:
        self._state = state
        self._window = window
        self._interval_ms = interval_ms
        self._active = False

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._schedule()

    def stop(self) -> None:
        self._active = False

    def _schedule(self) -> None:
        if not self._active:
            return
        sublime.set_timeout_async(self._poll, self._interval_ms)

    def _poll(self) -> None:
        if not self._active:
            return
        if not self._state.session_active:
            sync_selection_history(self._window)
        self._schedule()


def current_group_selection_state(window, group: int) -> GroupSelectionState | None:
    selected_sheets = list(window.selected_sheets_in_group(group))
    selected_identities = [
        sheet_identity(sheet, window) for sheet in selected_sheets if sheet.group() is not None
    ]
    if not selected_identities:
        return None

    active_sheet_index = None
    active_sheet = window.active_sheet_in_group(group)
    if active_sheet is not None and active_sheet.group() is not None:
        active_identity = sheet_identity(active_sheet, window)
        try:
            active_sheet_index = selected_identities.index(active_identity)
        except ValueError:
            active_sheet_index = None

    return {
        "active_sheet_index": active_sheet_index,
        "selected_sheets": selected_identities,
    }


def history_for_window(window) -> SheetSelectionHistory:
    history = window.settings().get(_HISTORY_KEY)
    if isinstance(history, dict) and is_current_history(history):
        return cast(SheetSelectionHistory, history)

    history = default_history()
    window.settings().set(_HISTORY_KEY, history)
    return history


def store_history(window, history: SheetSelectionHistory) -> None:
    window.settings().set(_HISTORY_KEY, history)


def default_history() -> SheetSelectionHistory:
    return {"groups": {}}


def is_current_history(history: dict[str, Any]) -> bool:
    groups = history.get("groups")
    if not isinstance(groups, dict):
        return False

    for group_state_stack in groups.values():
        if not isinstance(group_state_stack, list):
            return False
        for group_state in group_state_stack:
            if not isinstance(group_state, dict):
                return False
            if set(group_state) != {"active_sheet_index", "selected_sheets"}:
                return False
            if group_state["active_sheet_index"] is not None and not isinstance(
                group_state["active_sheet_index"], int
            ):
                return False
            if not isinstance(group_state["selected_sheets"], list):
                return False

    return True


def sync_selection_history(
    window,
    prune_removed_sheets: bool = False,
) -> SheetSelectionHistory:
    history = history_for_window(window)
    groups = history["groups"]
    changed = False

    if prune_removed_sheets:
        for group_key, group_state_stack in list(groups.items()):
            try:
                group = int(group_key)
            except TypeError, ValueError:
                # Unexpected/corrupt key; drop it to avoid crashing.
                del groups[group_key]
                changed = True
                continue

            updated_stack = prune_history_stack_for_live_sheets(window, group, group_state_stack)
            if updated_stack != group_state_stack:
                changed = True
                if updated_stack:
                    groups[group_key] = updated_stack
                else:
                    del groups[group_key]

    active_group = window.active_group()
    current = current_group_selection_state(window, active_group)
    if current is not None:
        group_key = str(active_group)
        existing_stack = groups.get(group_key, [])
        updated_stack = prepend_group_state(existing_stack, current)
        if updated_stack != existing_stack:
            groups[group_key] = updated_stack
            changed = True

    if changed:
        store_history(window, history)
    return history


def prepend_group_state(
    existing_stack: list[GroupSelectionState],
    current: GroupSelectionState,
) -> list[GroupSelectionState]:
    return prune_history_stack([current, *existing_stack])


def prune_history_stack_for_live_sheets(
    window,
    group: int,
    group_state_stack: list[GroupSelectionState],
) -> list[GroupSelectionState]:
    updated_stack: list[GroupSelectionState] = []

    for group_state in group_state_stack:
        pruned_group_state = prune_group_state_for_live_sheets(window, group, group_state)
        if pruned_group_state is not None:
            updated_stack.append(pruned_group_state)

    return updated_stack


def prune_group_state_for_live_sheets(
    window,
    group: int,
    group_state: GroupSelectionState,
) -> GroupSelectionState | None:
    selected_sheets = [
        identity
        for identity in group_state["selected_sheets"]
        if find_sheet_by_identity_and_group(window, identity, group) is not None
    ]
    if not selected_sheets:
        return None

    return {
        "active_sheet_index": prune_active_sheet_index(
            group_state["active_sheet_index"],
            group_state["selected_sheets"],
            selected_sheets,
        ),
        "selected_sheets": selected_sheets,
    }


def prune_active_sheet_index(
    active_sheet_index: int | None,
    original_selected_sheets: list[SheetIdentity],
    pruned_selected_sheets: list[SheetIdentity],
) -> int | None:
    if active_sheet_index is None:
        return None
    if active_sheet_index < 0 or active_sheet_index >= len(original_selected_sheets):
        return None

    active_identity = original_selected_sheets[active_sheet_index]
    try:
        return pruned_selected_sheets.index(active_identity)
    except ValueError:
        return 0 if pruned_selected_sheets else None


def prune_group_state(
    group_state: GroupSelectionState,
    seen_identities: list[SheetIdentity],
) -> GroupSelectionState | None:
    selected_sheets = [
        identity for identity in group_state["selected_sheets"] if identity not in seen_identities
    ]
    if not selected_sheets:
        return None

    seen_identities.extend(selected_sheets)
    return {
        "active_sheet_index": prune_active_sheet_index(
            group_state["active_sheet_index"],
            group_state["selected_sheets"],
            selected_sheets,
        ),
        "selected_sheets": selected_sheets,
    }


def prune_history_stack(
    group_state_stack: list[GroupSelectionState],
    removed_identities: list[SheetIdentity] | None = None,
) -> list[GroupSelectionState]:
    updated_stack: list[GroupSelectionState] = []
    seen_identities: list[SheetIdentity] = list(removed_identities or [])
    for group_state in group_state_stack:
        pruned_group_state = prune_group_state(
            group_state,
            seen_identities,
        )
        if pruned_group_state is not None:
            updated_stack.append(pruned_group_state)
    return updated_stack


def prune_sheet_from_history(window, sheet) -> None:
    state = get_state(window)
    sheet_id = sheet_identity(sheet, window)
    if state.session_origin_selection is not None:
        pruned_selected_sheets = [
            identity
            for identity in state.session_origin_selection["selected_sheets"]
            if identity != sheet_id
        ]
        if pruned_selected_sheets:
            state.session_origin_selection = {
                "active_sheet_index": prune_active_sheet_index(
                    state.session_origin_selection["active_sheet_index"],
                    state.session_origin_selection["selected_sheets"],
                    pruned_selected_sheets,
                ),
                "selected_sheets": pruned_selected_sheets,
            }
        else:
            state.session_origin_selection = None

    history = history_for_window(window)
    groups = history["groups"]
    changed = False

    for group, group_state_stack in list(groups.items()):
        updated_stack = prune_history_stack(group_state_stack, [sheet_id])

        if updated_stack != group_state_stack:
            if updated_stack:
                groups[group] = updated_stack
            else:
                del groups[group]
            changed = True

    if changed:
        store_history(window, history)
