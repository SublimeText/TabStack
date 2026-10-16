from __future__ import annotations

import sublime

from .constants import KIND_MODIFIED
from .ctrl_release import create_poller
from .settings import load_settings
from .sheets import apply_group_selection
from .state import TabStackWindowState

SHOW_PANEL_DELAY_MS = 150
# How long to keep a session pending past the panel delay while the Ctrl state is unknown.
CTRL_STATE_TIMEOUT_MS = 1000
CTRL_STATE_RETRY_MS = 10


def _ensure_ctrl_release_poller(window: sublime.Window, state: TabStackWindowState) -> None:
    if state.ctrl_release_poller:
        return

    def on_release() -> None:
        # A release queued before this poller was stopped must not commit a newer session.
        if state.ctrl_release_poller is not poller:
            return
        if state.session_active:
            _commit_session(window, state)
        elif state.session_pending:
            _commit_pending_session(window, state)

    poller = create_poller(on_release, 25)
    state.ctrl_release_poller = poller
    poller.start()


def show_panel(window: sublime.Window, state: TabStackWindowState) -> None:
    entries = state.session_entries
    if not state.session_active or not entries:
        return

    items = [
        sublime.QuickPanelItem(
            trigger=entry.caption[0],
            details=entry.caption[1],
            kind=KIND_MODIFIED if entry.dirty else sublime.KIND_AMBIGUOUS,
        )
        for entry in entries
    ]

    preview_tabs = bool(load_settings().get("preview_tabs", True))

    def on_select(index: int) -> None:
        if index < 0:
            handle_panel_closed(window, state)
            return
        state.session_selected_index = index
        _commit_session(window, state)

    def on_highlight(index: int) -> None:
        if index < 0 or index >= len(entries):
            return
        state.session_selected_index = index
        if preview_tabs:
            preview_entry(window, state)

    window.show_quick_panel(
        items,
        on_select,
        selected_index=state.session_selected_index,
        on_highlight=on_highlight,
        placeholder="Release ctrl to close; Hit ctrl+escape to abort",
    )

    _ensure_ctrl_release_poller(window, state)


def schedule_panel(window: sublime.Window, state: TabStackWindowState, *, token: int) -> None:
    _ensure_ctrl_release_poller(window, state)

    def open_if_still_pending(waited_ms: int) -> None:
        if not state.session_pending or state.session_pending_token != token:
            return
        poller = state.ctrl_release_poller
        ctrl_down = poller.is_ctrl_down() if poller is not None else True
        if ctrl_down is None and waited_ms < CTRL_STATE_TIMEOUT_MS:
            # A release reported meanwhile commits the pending session through the poller.
            sublime.set_timeout(
                lambda: open_if_still_pending(waited_ms + CTRL_STATE_RETRY_MS),
                CTRL_STATE_RETRY_MS,
            )
            return
        if ctrl_down is False:
            # Ctrl was released before the panel appeared; switch like a quick press would.
            _commit_pending_session(window, state)
            return
        state.session_active = True
        state.session_pending = False
        show_panel(window, state)

    sublime.set_timeout(lambda: open_if_still_pending(0), SHOW_PANEL_DELAY_MS)


def preview_entry(window: sublime.Window, state: TabStackWindowState) -> None:
    if state.session_entries is None:
        return
    if not 0 <= state.session_selected_index < len(state.session_entries):
        return
    entry = state.session_entries[state.session_selected_index]
    _ = apply_group_selection(window, entry.selection, state.session_group)


def _commit_pending_session(window: sublime.Window, state: TabStackWindowState) -> None:
    entries = state.session_entries
    if not entries:
        state.clear_session()
        return

    index = clamp_index(state.session_selected_index, len(entries))
    selection = entries[index].selection
    _ = apply_group_selection(window, selection, state.session_group)
    state.clear_session()


def _commit_session(window: sublime.Window, state: TabStackWindowState) -> None:
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


def cancel_session(window: sublime.Window, state: TabStackWindowState) -> None:
    if not state.session_active:
        if not state.session_pending:
            return
        state.clear_session()
        return

    origin = state.session_origin_selection
    window.run_command("hide_overlay", {"cancel": True})
    if origin is not None:
        _ = apply_group_selection(window, origin, state.session_group)
    state.clear_session()


def clamp_index(index: int, size: int) -> int:
    return max(0, min(index, size - 1))


def reopen_panel_at_index(window: sublime.Window, state: TabStackWindowState, index: int) -> None:
    if not state.session_active or state.session_panel_reopening:
        return

    entries = state.session_entries
    if not entries or len(entries) < 2:
        return

    state.session_selected_index = clamp_index(index, len(entries))
    state.session_panel_reopening = True
    window.run_command("hide_overlay", {"cancel": True})
    sublime.set_timeout(lambda: show_panel(window, state), 0)


def handle_panel_closed(window: sublime.Window, state: TabStackWindowState) -> None:
    if state.session_panel_reopening:
        state.session_panel_reopening = False
        return

    cancel_session(window, state)
