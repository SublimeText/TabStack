from __future__ import annotations

from pathlib import Path


def caption_for_sheet_identities(identities, window) -> list[str]:
    titles = [identity["name"] for identity in identities]
    paths = [
        _relative_path(identity["path"], window) for identity in identities if identity["path"]
    ]

    return [" | ".join(titles), " | ".join(paths)]


def _title_from_sheet(sheet) -> str:
    file_name = sheet.file_name()
    if file_name:
        return Path(file_name).name
    return "Untitled"


def _relative_path(file_name: str, window) -> str:
    absolute = Path(file_name)
    for folder in window.folders():
        try:
            relative = absolute.relative_to(folder)
        except ValueError:
            continue
        return str(relative)
    return str(absolute)
