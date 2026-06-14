from __future__ import annotations

from dataclasses import dataclass

from ._compat import sublime, sublime_plugin
from .captions import caption_for_view
from .ctrl_release import CtrlReleasePoller, is_available
from .state import get_state


@dataclass(slots=True)
class _Entry:
    view_id: int
    caption: list[str]


class ShowTabStackCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        window = self.window
        if window is None:
            return

        if not is_available():
            return

        state = get_state(window)
        entries = _collect_entries(window, state)
        if not entries:
            return

        state.session_active = True
        state.session_origin_view_id = _active_view_id(window)
        state.session_selected_index = _initial_index(state, entries)
        _show_panel(window, state, entries)

        state.poller = CtrlReleasePoller(lambda: _commit_on_release(window, state), 25)
        state.poller.start()


class TabStackCommitCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        window = self.window
        if window is None:
            return

        state = get_state(window)
        _commit_session(window, state)


class TabStackCancelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        window = self.window
        if window is None:
            return

        state = get_state(window)
        _cancel_session(window, state)


def _collect_entries(window, state) -> list[_Entry]:
    active_group_ids = {view.id() for view in window.views_in_group(window.active_group())}
    entries: list[_Entry] = []
    pruned_mru_ids: list[int] = []

    hydrate_mru_state(state, window)

    for view_id in state.mru_view_ids:
        view = _find_view_by_id(window, view_id)
        if view is None:
            continue
        pruned_mru_ids.append(view_id)
        if view_id not in active_group_ids:
            continue
        entries.append(_Entry(view_id=view_id, caption=caption_for_view(view, window)))

    state.mru_view_ids = pruned_mru_ids
    return entries


def hydrate_mru_state(state, window) -> None:
    if state.mru_initialized:
        return

    state.mru_view_ids = _initial_view_ids(window.views())
    state.mru_initialized = True


def _initial_view_ids(views) -> list[int]:
    tab_views = list(enumerate(views))
    tab_views.sort(key=lambda item: _activation_sort_key(item[1], item[0]))
    return [view.id() for _, view in tab_views]


def _activation_sort_key(view, fallback_index: int) -> tuple[bool, float, int]:
    value = view.settings().get("tab_stack.last_activated")
    if value is None:
        return True, 0.0, fallback_index
    return False, -float(value), fallback_index


def _active_view_id(window) -> int | None:
    view = window.active_view()
    if view is None:
        return None
    return view.id()


def _initial_index(state, entries: list[_Entry]) -> int:
    origin_id = state.session_origin_view_id
    if origin_id is None:
        return 0
    for entry in entries:
        if entry.view_id == origin_id:
            return 1 if len(entries) > 1 else 0
    return 0


def _show_panel(window, state, entries: list[_Entry]) -> None:
    items = [entry.caption for entry in entries]

    def on_select(index: int) -> None:
        if index < 0:
            _handle_panel_closed(window, state)
            return
        state.session_selected_index = index
        _commit_session(window, state)

    def on_highlight(index: int) -> None:
        if index < 0 or index >= len(entries):
            return
        state.session_selected_index = index
        _preview_entry(window, state, entries[index])

    window.show_quick_panel(
        items,
        on_select,
        selected_index=state.session_selected_index,
        on_highlight=on_highlight,
        placeholder="Release ctrl to close; Hit ctrl+escape to abort",
    )
    if entries:
        _preview_entry(window, state, entries[state.session_selected_index])


def _preview_entry(window, state, entry: _Entry) -> None:
    if state.session_preview_view_id == entry.view_id:
        return

    view = _find_view_by_id(window, entry.view_id)
    if view is None:
        return

    state.session_preview_view_id = entry.view_id
    window.focus_view(view)


def _commit_on_release(window, state) -> None:
    if not state.session_active:
        return
    _commit_session(window, state)


def _commit_session(window, state) -> None:
    if not state.session_active:
        return

    entries = _collect_entries(window, state)
    if not entries:
        _cancel_session(window, state)
        return

    index = _clamp_index(state.session_selected_index, len(entries))
    view = _find_view_by_id(window, entries[index].view_id)
    if view is None:
        _cancel_session(window, state)
        return

    _promote_view_id(state, view.id())
    _finish_session(window, state)
    window.run_command("hide_overlay", {"cancel": True})
    window.focus_view(view)


def _cancel_session(window, state) -> None:
    if not state.session_active:
        return

    origin_id = state.session_origin_view_id
    origin_view = _find_view_by_id(window, origin_id) if origin_id is not None else None
    _finish_session(window, state)
    window.run_command("hide_overlay", {"cancel": True})
    if origin_view is not None:
        window.focus_view(origin_view)


def _finish_session(window, state) -> None:
    state.session_tagged_view_ids.clear()
    state.clear_session()


def _promote_view_id(state, view_id: int) -> None:
    state.mru_view_ids = [item for item in state.mru_view_ids if item != view_id]
    state.mru_view_ids.insert(0, view_id)


def _clamp_index(index: int, size: int) -> int:
    if size <= 0:
        return 0
    if index < 0:
        return 0
    if index >= size:
        return size - 1
    return index


def _find_view_by_id(window, view_id: int | None):
    if view_id is None:
        return None
    view = sublime.View(view_id)
    view_window = view.window()
    if view_window is None:
        return None
    if view_window.id() != window.id():
        return None
    return view


def _handle_panel_closed(window, state) -> None:
    _cancel_session(window, state)
