from __future__ import annotations

from ._compat import sublime
from .ctrl_release import CtrlReleasePoller
from .sheets import apply_group_selection
from .state import TabStackWindowState

SHOW_PANEL_DELAY_MS = 150


def _ensure_ctrl_release_poller(window, state) -> None:
    if state.ctrl_release_poller:
        return

    def on_release() -> None:
        if state.session_active:
            _commit_session(window, state)
        elif state.session_pending:
            state.clear_session()

    state.ctrl_release_poller = CtrlReleasePoller(on_release, 25)
    state.ctrl_release_poller.start()


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

    _ensure_ctrl_release_poller(window, state)


def schedule_panel(window, state, *, token: int) -> None:
    _ensure_ctrl_release_poller(window, state)

    def open_if_still_pending() -> None:
        if not state.session_pending or state.session_pending_token != token:
            return
        if state.ctrl_release_poller is not None and not state.ctrl_release_poller.is_ctrl_down():
            state.clear_session()
            return
        state.session_active = True
        state.session_pending = False
        show_panel(window, state)

    sublime.set_timeout(open_if_still_pending, SHOW_PANEL_DELAY_MS)


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
        if not state.session_pending:
            return
        state.clear_session()
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
