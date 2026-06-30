from __future__ import annotations

from ._compat import sublime, sublime_plugin
from .ctrl_release import is_available
from .history import (
    SelectionHistoryPoller,
    history_for_window,
    prune_sheet_from_history,
    sync_selection_history,
)
from .sheets import apply_group_selection
from .state import get_state, remove_window_state


def _ensure_selection_poller(window, state) -> None:
    if state.selection_poller is None:
        state.selection_poller = SelectionHistoryPoller(state, window)
        state.selection_poller.start()


def _session_boundary_value(window, key: str) -> bool:
    state = get_state(window)
    if not state.session_active:
        return False
    if key == "tab_stack.session_active":
        return True

    entries = state.session_entries
    if not entries or len(entries) < 2:
        return False
    if key == "tab_stack.quick_panel_at_top":
        return state.session_selected_index == 0
    if key == "tab_stack.quick_panel_at_bottom":
        return state.session_selected_index == len(entries) - 1
    return False


class TabStackListener(sublime_plugin.EventListener):
    def on_activated(self, view) -> None:
        window = view.window()
        if window is None:
            return

        state = get_state(window)
        if state.session_active:
            return

        _ensure_selection_poller(window, state)
        sync_selection_history(window)

    def on_query_context(self, view, key, operator, operand, match_all):
        if key == "tab_stack.ctrl_release_available":
            value = is_available()
        elif key in {
            "tab_stack.session_active",
            "tab_stack.quick_panel_at_top",
            "tab_stack.quick_panel_at_bottom",
        }:
            if view is None:
                return False

            window = view.window()
            if window is None:
                return False

            value = _session_boundary_value(window, key)
        else:
            return None

        if operator == sublime.OP_EQUAL:
            return value == bool(operand)
        if operator == sublime.OP_NOT_EQUAL:
            return value != bool(operand)
        return None

    def on_close(self, view) -> None:
        window = view.window()
        if window is not None:
            sheet = view.sheet()
            if sheet is not None:
                prune_sheet_from_history(window, sheet)
        if window is not None and not window.views():
            remove_window_state(window.id())

    def on_pre_close(self, view) -> None:
        sheet = view.sheet()
        if sheet is None or sheet.is_transient() or sheet.is_semi_transient():
            return

        window = view.window()
        if window is None:
            return

        state = get_state(window)
        if state.session_active:
            return

        history = history_for_window(window)
        group_state_stack = history["groups"].get(str(sheet.group()))
        if group_state_stack is None or len(group_state_stack) < 2:
            return

        previous_selection = group_state_stack[1]
        apply_group_selection(window, previous_selection, sheet.group())
