from .commands import *  # noqa: F401,F403
from .ctrl_release import plugin_unloaded as _ctrl_release_plugin_unloaded
from .listener import *  # noqa: F401,F403
from .state import iter_states as _iter_states


def plugin_unloaded() -> None:
    for state in _iter_states():
        if state.selection_poller is not None:
            state.selection_poller.stop()
            state.selection_poller = None
        if state.ctrl_release_poller is not None:
            state.ctrl_release_poller.stop()
            state.ctrl_release_poller = None

    _ctrl_release_plugin_unloaded()
