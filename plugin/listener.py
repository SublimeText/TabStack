from __future__ import annotations

from time import time

from ._compat import sublime, sublime_plugin
from .commands import hydrate_mru_state
from .state import get_state, remove_view_from_all, remove_window_state


class TabStackListener(sublime_plugin.EventListener):
    def on_activated(self, view) -> None:
        if view is None:
            return
        window = view.window()
        if window is None:
            return

        state = get_state(window)
        if not state.mru_initialized:
            hydrate_mru_state(state, window.views())
            return

        hydrate_mru_state(state, window.views())
        if state.session_active:
            return

        view_id = view.id()
        view.settings().set("tab_stack.last_activated", time())
        state.mru_view_ids = [item for item in state.mru_view_ids if item != view_id]
        state.mru_view_ids.insert(0, view_id)

    def on_query_context(self, view, key, operator, operand, match_all):
        if key != "tab_stack.quick_panel":
            return None

        if view is None:
            return False

        window = view.window()
        if window is None:
            return False

        state = get_state(window)
        value = state.session_active
        if operator == sublime.OP_EQUAL:
            return value == bool(operand)
        if operator == sublime.OP_NOT_EQUAL:
            return value != bool(operand)
        return None

    def on_close(self, view) -> None:
        if view is None:
            return
        remove_view_from_all(view.id())
        window = view.window()
        if window is not None and not window.views():
            remove_window_state(window.id())
