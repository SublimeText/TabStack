from __future__ import annotations

from ._compat import sublime_plugin
from .ctrl_release import is_available
from .history import current_group_selection_state, sync_selection_history
from .mru import collect_entries
from .session import cancel_session, reopen_panel_at_index, schedule_panel, show_panel
from .state import get_state


class TabStackOpenCommand(sublime_plugin.WindowCommand):
    def run(self, *, forward=True, selected_index: int = 1) -> None:
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

        if state.session_pending:
            state.session_pending = False
            state.session_pending_token += 1
            state.session_active = True
            state.session_selected_index = selected_index
            show_panel(window, state)
            return

        active_group = window.active_group()
        state.session_origin_selection = current_group_selection_state(window, active_group)
        history = sync_selection_history(window, prune_removed_sheets=True)
        entries = collect_entries(window, history)
        if not entries:
            return

        state.session_pending = True
        state.session_pending_token += 1
        state.session_group = active_group
        state.session_entries = entries
        state.session_selected_index = selected_index
        schedule_panel(window, state, token=state.session_pending_token)


class TabStackCancelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        window = self.window
        if window is None:
            return

        state = get_state(window)
        cancel_session(window, state)


class TabStackCycleCommand(sublime_plugin.WindowCommand):
    def run(self, *, forward: bool) -> None:
        window = self.window
        if window is None:
            return

        state = get_state(window)
        entries = state.session_entries
        if not state.session_active or not entries or len(entries) < 2:
            return

        target_index = 0 if forward else len(entries) - 1
        reopen_panel_at_index(window, state, target_index)
