from __future__ import annotations

import sublime

SETTINGS_FILE = "TabStack.sublime-settings"


def load_settings() -> sublime.Settings:
    return sublime.load_settings(SETTINGS_FILE)


def save_settings() -> None:
    sublime.save_settings(SETTINGS_FILE)
