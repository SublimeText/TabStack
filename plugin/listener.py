from __future__ import annotations

from typing import TYPE_CHECKING

import sublime
import sublime_plugin

from .ctrl_release import is_available
from .history import (
    SelectionHistoryPoller,
    history_for_window,
    prune_sheet_from_history,
    sync_selection_history,
)
from .sheets import apply_group_selection
from .state import TabStackWindowState, get_state, remove_window_state

if TYPE_CHECKING:
    from sublime_types import Value


def _ensure_selection_poller(window: sublime.Window, state: TabStackWindowState) -> None:
    if state.selection_poller is None:
        poller = SelectionHistoryPoller(state, window)
        state.selection_poller = poller
        poller.start()


def _is_widget_view(view: sublime.View) -> bool:
    """Whether the view is an overlay/panel widget rather than a tab.

    `View.element` is not usable for this: output views report an element
    even when they live in a real tab, most notably the Find Results buffer
    ("find_in_files:output"), but also build output ("exec:output").
    Only views without a backing sheet are actual widgets.
    """
    return view.sheet_id() == 0


def _session_boundary_value(window: sublime.Window, key: str) -> bool:
    state = get_state(window)
    if key == "tab_stack.session_pending":
        return state.session_pending
    if not state.session_active:
        return False
    if key == "tab_stack.session_active":
        return state.session_active

    entries = state.session_entries
    if not entries or len(entries) < 2:
        return False
    if key == "tab_stack.quick_panel_at_top":
        return state.session_selected_index == 0
    if key == "tab_stack.quick_panel_at_bottom":
        return state.session_selected_index == len(entries) - 1
    return False


class TabStackListener(sublime_plugin.EventListener):
    def on_activated(self, view: sublime.View) -> None:
        window = view.window()
        if window is None:
            return

        state = get_state(window)

        if _is_widget_view(view):
            state.overlay_views.add(view.id())
            return

        if state.session_active or state.session_pending or state.overlay_active:
            return

        _ensure_selection_poller(window, state)
        _ = sync_selection_history(window)

    def on_deactivated(self, view: sublime.View) -> None:
        window = view.window()
        if window is None:
            return

        get_state(window).overlay_views.discard(view.id())

    def on_query_context(
        self,
        # `view` is widened because ST may query contexts without a view.
        view: sublime.View | None,
        key: str,
        operator: sublime.QueryOperator,
        operand: Value,
        match_all: bool,
    ) -> bool | None:
        if key == "tab_stack.ctrl_release_available":
            value = is_available()
        elif key in {
            "tab_stack.session_active",
            "tab_stack.session_pending",
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

    def on_close(self, view: sublime.View) -> None:
        window = view.window()
        if window is not None:
            # A widget destroyed without a deactivation would otherwise
            # pin `overlay_active` and freeze history syncing for the window.
            get_state(window).overlay_views.discard(view.id())
            sheet = view.sheet()
            if sheet is not None:
                prune_sheet_from_history(window, sheet)
        if window is not None and not window.views():
            remove_window_state(window.id())

    def on_pre_close(self, view: sublime.View) -> None:
        sheet = view.sheet()
        if sheet is None or sheet.is_transient() or sheet.is_semi_transient():
            return

        group = sheet.group()
        if group is None:
            return

        window = view.window()
        if window is None:
            return

        # Closing an inactive tab does not change the focus,
        # so there is nothing to restore.
        if window.active_sheet_in_group(group) != sheet:
            return

        state = get_state(window)
        if state.session_active:
            return

        history = history_for_window(window)
        group_state_stack = history["groups"].get(str(group))
        if group_state_stack is None or len(group_state_stack) < 2:
            return

        previous_selection = group_state_stack[1]
        _ = apply_group_selection(window, previous_selection, group)
