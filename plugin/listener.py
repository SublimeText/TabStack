from __future__ import annotations

from time import time

from ._compat import sublime, sublime_plugin
from .commands import hydrate_mru_state
from .ctrl_release import is_available
from .state import get_state, remove_view_from_all, remove_window_state


class TabStackListener(sublime_plugin.EventListener):
    def on_activated(self, view) -> None:
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
        if key == "tab_stack.ctrl_release_available":
            value = is_available()
        elif key == "tab_stack.quick_panel":
            if view is None:
                return False

            window = view.window()
            if window is None:
                return False

            state = get_state(window)
            value = state.session_active
        else:
            return None

        if operator == sublime.OP_EQUAL:
            return value == bool(operand)
        if operator == sublime.OP_NOT_EQUAL:
            return value != bool(operand)
        return None

    def on_close(self, view) -> None:
        remove_view_from_all(view.id())
        window = view.window()
        if window is not None and not window.views():
            remove_window_state(window.id())

    def on_pre_close(self, view) -> None:
        window = view.window()
        if window is None:
            return

        state = get_state(window)
        if not state.mru_initialized:
            hydrate_mru_state(state, window.views())

        closing_view_id = view.id()
        open_views = window.views()
        for view_id in state.mru_view_ids:
            if view_id == closing_view_id:
                continue
            for next_view in open_views:
                if next_view.id() == view_id:
                    window.focus_view(next_view)
                    return
