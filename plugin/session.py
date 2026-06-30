from __future__ import annotations

from ._compat import sublime
from .ctrl_release import CtrlReleasePoller
from .sheets import apply_group_selection
from .state import TabStackWindowState


def show_panel(window, state) -> None:
    if not state.session_active or not state.session_entries:
        return

    items = [entry.caption for entry in state.session_entries]

    def on_select(index: int) -> None:
        if index < 0:
            handle_panel_closed(window, state)
            return
        state.session_selected_index = index
        _commit_session(window, state)

    def on_highlight(index: int) -> None:
        if index < 0 or index >= len(state.session_entries):
            return
        state.session_selected_index = index
        preview_entry(window, state)

    window.show_quick_panel(
        items,
        on_select,
        selected_index=state.session_selected_index,
        on_highlight=on_highlight,
        placeholder="Release ctrl to close; Hit ctrl+escape to abort",
    )

    if not state.ctrl_release_poller:
        state.ctrl_release_poller = CtrlReleasePoller(
            lambda: _commit_session(window, state),
            25,
        )
        state.ctrl_release_poller.start()


def preview_entry(window, state: TabStackWindowState) -> None:
    if state.session_entries is None:
        return
    if not 0 <= state.session_selected_index < len(state.session_entries):
        return
    entry = state.session_entries[state.session_selected_index]
    apply_group_selection(window, entry.selection, state.session_group)


def _commit_session(window, state) -> None:
    if not state.session_active:
        return

    entries = state.session_entries
    if not entries:
        cancel_session(window, state)
        return

    index = clamp_index(state.session_selected_index, len(entries))
    selection = entries[index].selection
    if not apply_group_selection(window, selection, state.session_group):
        cancel_session(window, state)
        return

    window.run_command("hide_overlay", {"cancel": True})
    state.clear_session()


def cancel_session(window, state) -> None:
    if not state.session_active:
        return

    origin = state.session_origin_selection
    window.run_command("hide_overlay", {"cancel": True})
    if origin is not None:
        apply_group_selection(window, origin, state.session_group)
    state.clear_session()


def clamp_index(index: int, size: int) -> int:
    return max(0, min(index, size - 1))


def reopen_panel_at_index(window, state: TabStackWindowState, index: int) -> None:
    if not state.session_active or state.session_panel_reopening:
        return

    entries = state.session_entries
    if not entries or len(entries) < 2:
        return

    state.session_selected_index = clamp_index(index, len(entries))
    state.session_panel_reopening = True
    window.run_command("hide_overlay", {"cancel": True})
    sublime.set_timeout(lambda: show_panel(window, state), 0)


def handle_panel_closed(window, state) -> None:
    if state.session_panel_reopening:
        state.session_panel_reopening = False
        return

    cancel_session(window, state)
