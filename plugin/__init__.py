from .commands import *  # noqa: F401,F403
from .ctrl_release import plugin_unloaded as _ctrl_release_plugin_unloaded
from .listener import *  # noqa: F401,F403
from .state import iter_states


def plugin_unloaded() -> None:
    for state in iter_states():
        if state.poller is not None:
            state.poller.stop()
            state.poller = None

    _ctrl_release_plugin_unloaded()
