from __future__ import annotations

from types import SimpleNamespace

try:
    import sublime  # type: ignore
    import sublime_plugin  # type: ignore
except ImportError:  # pragma: no cover - used outside Sublime Text.

    class _Settings(dict):
        def get(self, key, default=None):
            return super().get(key, default)

        def set(self, key, value):
            self[key] = value

        def erase(self, key):
            self.pop(key, None)

    class _QuickPanelItem:
        __slots__ = ["trigger", "details", "annotation", "kind"]

        def __init__(self, trigger, details="", annotation="", kind=(0, "", "")):
            self.trigger = trigger
            self.details = details
            self.annotation = annotation
            self.kind = kind

    class _SublimeModule(SimpleNamespace):
        OP_EQUAL = 0
        OP_NOT_EQUAL = 1
        KEEP_OPEN_ON_FOCUS_LOST = 0
        MONOSPACE_FONT = 0
        KIND_ID_COLOR_ORANGISH = 10
        KIND_AMBIGUOUS = (0, "", "")
        QuickPanelItem = _QuickPanelItem

        def set_timeout(self, callback, timeout=0):
            callback()

        def set_timeout_async(self, callback, timeout=0):
            callback()

        def active_window(self):
            return None

    class _CommandBase:
        def __init__(self, window=None):
            self.window = window

    class _EventListener:
        pass

    sublime = _SublimeModule(Settings=_Settings)
    sublime_plugin = SimpleNamespace(
        WindowCommand=_CommandBase,
        EventListener=_EventListener,
    )
