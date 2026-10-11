from __future__ import annotations

import sublime

SETTINGS_FILE = "TabStack.sublime-settings"
_settings = sublime.load_settings(SETTINGS_FILE)


def save_settings() -> None:
    sublime.save_settings(SETTINGS_FILE)


def preview_file() -> bool:
    """Whether the highlighted list entry is shown before the list closes."""
    return _bool_setting("preview_file", default=True)


def _bool_setting(key: str, *, default: bool) -> bool:
    value = _settings.get(key, default)
    return value if isinstance(value, bool) else default
