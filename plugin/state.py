from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TabStackWindowState:
    window_id: int
    mru_view_ids: list[int] = field(default_factory=list)
    mru_initialized: bool = False
    session_active: bool = False
    session_origin_view_id: int | None = None
    session_selected_index: int = 0
    session_preview_view_id: int | None = None
    session_tagged_view_ids: set[int] = field(default_factory=set)
    poller: Any = None

    def clear_session(self) -> None:
        self.session_active = False
        self.session_origin_view_id = None
        self.session_selected_index = 0
        self.session_preview_view_id = None
        if self.poller is not None:
            self.poller.stop()
            self.poller = None


_WINDOW_STATE: dict[int, TabStackWindowState] = {}


def get_state(window) -> TabStackWindowState:
    window_id = window.id()
    state = _WINDOW_STATE.get(window_id)
    if state is None:
        state = TabStackWindowState(window_id=window_id)
        _WINDOW_STATE[window_id] = state
    return state


def remove_window_state(window_id: int) -> None:
    state = _WINDOW_STATE.pop(window_id, None)
    if state is not None and state.poller is not None:
        state.poller.stop()


def remove_view_from_all(view_id: int) -> None:
    for state in _WINDOW_STATE.values():
        state.mru_view_ids = [item for item in state.mru_view_ids if item != view_id]
        state.session_tagged_view_ids.discard(view_id)
        if state.session_preview_view_id == view_id:
            state.session_preview_view_id = None
        if state.session_origin_view_id == view_id:
            state.session_origin_view_id = None


def iter_states():
    return list(_WINDOW_STATE.values())
