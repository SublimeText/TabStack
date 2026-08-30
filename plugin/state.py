from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

import sublime

from .models import Entry, GroupSelectionState


class Poller(Protocol):
    """The part of a poller the window state has to know about."""

    def stop(self) -> None: ...


class CtrlPoller(Poller, Protocol):
    def is_ctrl_down(self) -> bool: ...


@dataclass
class TabStackWindowState:
    session_active: bool = False
    session_pending: bool = False
    session_pending_token: int = 0
    """Monotonically incremented token to track and implicitly cancel set_timeout callbacks."""
    session_origin_selection: Optional[GroupSelectionState] = None
    session_selected_index: int = 0
    session_group: int = 0
    session_entries: Optional[list[Entry]] = None
    session_panel_reopening: bool = False
    selection_poller: Optional[Poller] = None
    ctrl_release_poller: Optional[CtrlPoller] = None
    overlay_views: set[int] = field(default_factory=set)
    """Ids of the currently focused overlay/quick-panel widget views.

    We track ids rather than a count so a widget deactivating while another
    is still open doesn't prematurely re-enable history syncing,
    and so an unpaired activation or deactivation cannot desynchronize
    the flag permanently.
    Example widgets are goto anything, goto symbol/reference or find panels.
    """

    @property
    def overlay_active(self) -> bool:
        return bool(self.overlay_views)

    def clear_session(self) -> None:
        self.session_active = False
        self.session_pending = False
        self.session_origin_selection = None
        self.session_selected_index = 0
        self.session_group = 0
        self.session_entries = None
        self.session_panel_reopening = False
        self.session_pending_token += 1
        if self.ctrl_release_poller is not None:
            self.ctrl_release_poller.stop()
            self.ctrl_release_poller = None


_WINDOW_STATE: dict[int, TabStackWindowState] = {}


def get_state(window: sublime.Window) -> TabStackWindowState:
    window_id = window.id()
    state = _WINDOW_STATE.get(window_id)
    if state is None:
        state = TabStackWindowState()
        _WINDOW_STATE[window_id] = state
    return state


def remove_window_state(window_id: int) -> None:
    state = _WINDOW_STATE.pop(window_id, None)
    if state is not None:
        if state.selection_poller is not None:
            state.selection_poller.stop()
        if state.ctrl_release_poller is not None:
            state.ctrl_release_poller.stop()


def iter_states() -> list[TabStackWindowState]:
    return list(_WINDOW_STATE.values())
