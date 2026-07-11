from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, TypedDict

from .sheets import SheetIdentity

if TYPE_CHECKING:
    from .mru import Entry


class GroupSelectionState(TypedDict):
    active_sheet_index: Optional[int]
    selected_sheets: list[SheetIdentity]


class SheetSelectionHistory(TypedDict):
    # Only strings may be used as keys in ST settings.
    groups: dict[str, list[GroupSelectionState]]


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
    selection_poller: Any = None
    ctrl_release_poller: Any = None
    overlay_depth: int = 0
    """Counter for nested overlay/quick-panel widget focus tracking.

    We use a counter so a widget deactivating while another is still open
    doesn't prematurely re-enable history syncing.
    Example widgets are goto anything, goto symbol/reference or find panels.
    """

    @property
    def overlay_active(self) -> bool:
        return self.overlay_depth > 0

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


def get_state(window) -> TabStackWindowState:
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
