from __future__ import annotations

from pathlib import Path

import sublime

from .models import SheetIdentity


def caption_for_sheet_identities(
    identities: list[SheetIdentity],
    window: sublime.Window,
) -> list[str]:
    titles = [identity["name"] or _title_from_path(identity["path"]) for identity in identities]
    paths = [_relative_path(path, window) for identity in identities if (path := identity["path"])]

    return [" | ".join(titles), " | ".join(paths)]


def _title_from_path(file_name: str | None) -> str:
    if file_name:
        return Path(file_name).name
    return "Untitled"


def _relative_path(file_name: str, window: sublime.Window) -> str:
    absolute = Path(file_name)
    for folder in window.folders():
        try:
            relative = absolute.relative_to(folder)
        except ValueError:
            continue
        return str(relative)
    return str(absolute)
