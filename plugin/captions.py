from __future__ import annotations

from pathlib import Path


def caption_for_view(view, window) -> list[str]:
    title = view.name() or (Path(view.file_name()).name if view.file_name() else "Untitled")
    path = ""
    file_name = view.file_name()
    if file_name:
        path = _relative_path(file_name, window)
    return [title, path]


def _relative_path(file_name: str, window) -> str:
    absolute = Path(file_name)
    for folder in window.folders():
        try:
            relative = absolute.relative_to(folder)
        except ValueError:
            continue
        return str(relative)
    return str(absolute)
