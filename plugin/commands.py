from __future__ import annotations

from ._compat import sublime_plugin
from .ctrl_release import is_available
from .history import current_group_selection_state, sync_selection_history
from .mru import collect_entries
from .session import cancel_session, show_panel
from .state import get_state


class ShowTabStackCommand(sublime_plugin.WindowCommand):
    def run(self, *, forward=True) -> None:
        window = self.window
        if window is None:
            return
        elif not is_available():
            window.run_command("next_view_in_stack" if forward else "prev_view_in_stack")
            return
        elif not forward:
            # This is a fake binding.
            return

        state = get_state(window)
        active_group = window.active_group()
        state.session_origin_selection = current_group_selection_state(window, active_group)
        history = sync_selection_history(window, prune_removed_sheets=True)
        entries = collect_entries(window, history)
        if not entries:
            return

        state.session_active = True
        state.session_group = active_group
        state.session_entries = entries
        show_panel(window, state)


class TabStackCancelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        window = self.window
        if window is None:
            return

        state = get_state(window)
        cancel_session(window, state)
