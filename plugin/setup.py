from __future__ import annotations

import os
import shlex

import sublime
import sublime_plugin

from .ctrl_release import is_native_wayland, refresh_availability
from .ctrl_release.keystate_helper import (
    DEFAULT_HELPER_PATH,
    HelperProbe,
    HelperStatus,
    get_helper_probe,
)

__all__ = ["TabStackSetupKeystateHelperCommand"]

assert __package__ is not None
# This module lives in the `plugin` subpackage; resources are addressed by the top-level package.
_PACKAGE_NAME = __package__.split(".")[0]
_SETTINGS_FILE = "TabStack.sublime-settings"
_SOURCE_NAME = "tabstack-keystate.c"
_SETUP_COMMAND = "tab_stack_setup_keystate_helper"
_SETUP_CAPTION = "TabStack: Set Up Ctrl Detection for Wayland"

_wayland_dialog_shown = False


class TabStackSetupKeystateHelperCommand(sublime_plugin.WindowCommand):
    def is_visible(self) -> bool:
        return sublime.platform() == "linux"

    def run(self) -> None:
        # Re-probing makes this command double as the "check again" step.
        sublime.status_message("TabStack: checking the tabstack-keystate helper...")
        refresh_availability(self._on_probed)

    def _on_probed(self) -> None:
        probe = get_helper_probe()
        if probe is None:
            # The helper is only probed on Linux.
            return
        path = probe.path
        if probe.status is HelperStatus.OK:
            sublime.message_dialog(
                f"Ctrl detection via the tabstack-keystate helper at {path} works."
            )
            return

        extraction_dir = os.path.join(sublime.cache_path(), "TabStack", "keystate")
        try:
            source_path = _extract_source(extraction_dir)
        except OSError as exc:
            sublime.error_message(f"TabStack: could not extract the helper source: {exc}")
            return

        window = self.window
        _ = window.open_file(source_path)
        view = window.new_file(syntax="Packages/Markdown/Markdown.sublime-syntax")
        view.set_name("TabStack Setup")
        view.set_scratch(True)
        view.run_command(
            "append", {"characters": _instructions(probe, extraction_dir, source_path)}
        )
        view.set_read_only(True)


def offer_wayland_setup(window: sublime.Window) -> bool:
    """Show the setup dialog once per plugin load on native Wayland.

    Returns whether the dialog was shown.
    """
    global _wayland_dialog_shown
    if _wayland_dialog_shown or not is_native_wayland():
        return False
    if get_helper_probe() is None:
        # The background probe has not finished; the helper may still turn out to work.
        return False
    settings = sublime.load_settings(_SETTINGS_FILE)
    if not settings.get("show_wayland_setup_dialog", True):
        return False

    _wayland_dialog_shown = True
    result = sublime.yes_no_cancel_dialog(
        _DIALOG_MESSAGE,
        yes_title="Show Setup",
        no_title="Don't Ask Again",
    )
    if result == sublime.DIALOG_YES:
        window.run_command(_SETUP_COMMAND)
    elif result == sublime.DIALOG_NO:
        settings.set("show_wayland_setup_dialog", False)
        sublime.save_settings(_SETTINGS_FILE)
    return True


def _extract_source(extraction_dir: str) -> str:
    source = sublime.load_binary_resource(f"Packages/{_PACKAGE_NAME}/keystate/{_SOURCE_NAME}")
    os.makedirs(extraction_dir, exist_ok=True)
    source_path = os.path.join(extraction_dir, _SOURCE_NAME)
    with open(source_path, "wb") as file:
        _ = file.write(source)
    return source_path


def _instructions(probe: HelperProbe, extraction_dir: str, source_path: str) -> str:
    quoted_path = shlex.quote(probe.path)
    custom_path_note = _CUSTOM_PATH_NOTE if probe.path != DEFAULT_HELPER_PATH else ""
    return _INSTRUCTIONS.format(
        caption=_SETUP_CAPTION,
        status=probe.status.name,
        detail=probe.detail,
        status_note=_STATUS_NOTES.get(probe.status, ""),
        source_path=source_path,
        extraction_dir=shlex.quote(extraction_dir),
        helper_path=quoted_path,
        custom_path_note=custom_path_note,
    )


_DIALOG_MESSAGE = """\
TabStack cannot detect when Ctrl is released under native Wayland \
without the tabstack-keystate helper, \
so Ctrl+Tab falls back to Sublime Text's built-in tab cycling.

Show the instructions for setting up the helper?"""

_STATUS_NOTES = {
    HelperStatus.OUTDATED: """
The installed helper speaks a different protocol version than this version of TabStack expects,
usually because the package was updated.
Rebuild it from the extracted source and run the install and grant commands again.
""",
    HelperStatus.NO_ACCESS: """
The helper runs but cannot open the keyboard devices.
Usually its capability is missing, e.g. because the binary was replaced.
Run the install and grant commands below again.
""",
}

_CUSTOM_PATH_NOTE = """
The helper path comes from the `keystate_helper_path` setting.
Its file system must not be mounted with `nosuid`,
or the kernel ignores the file capability.
"""

_INSTRUCTIONS = """\
# {caption}

Status: {status}
{detail}
{status_note}
## Why a helper is needed

Sublime Text does not tell plugins when a key is released,
so TabStack polls the global keyboard state to notice when Ctrl is released.
A native Wayland session has no such global key state.
The `tabstack-keystate` helper reads the Ctrl state
from the kernel's input devices (`/dev/input/event*`) instead
and reports changes to TabStack on its standard output.

## Security implications

Review the helper's source before building it.
It was extracted to `{source_path}` and opened in another tab.

- The input devices are only readable by root (and usually the `input` group).
  The helper is therefore granted the `cap_dac_read_search` file capability,
  which allows reading *any* file on the system, not only input devices.
- At startup, the helper sets `no_new_privs`,
  opens every `/dev/input/event*` device read-only,
  keeps only the devices that advertise a Ctrl key,
  and then drops all capabilities before it reports any state.
- Any local user can run the helper
  and read through it whether Ctrl is held on any keyboard of this machine.
  It reports nothing but the Ctrl state.
- The capability is attached to the installed file.
  Replacing the file, e.g. after rebuilding, drops the capability,
  so run the grant command again after every install.

## Setup

Building needs a C compiler and the kernel headers;
`setcap` usually comes with the libcap tools package.
Build the helper, install it, and grant it the capability:

```sh
cd {extraction_dir}
cc -std=c11 -O2 -Wall -Wextra -o tabstack-keystate tabstack-keystate.c
sudo install -D -o root -g root -m 0755 tabstack-keystate {helper_path}
sudo setcap cap_dac_read_search=ep {helper_path}
```

Then run `{caption}` from the Command Palette again
to verify that the helper works.
{custom_path_note}
Flatpak and Snap builds of Sublime Text are not supported:
their sandbox makes the kernel ignore file capabilities
when Sublime Text runs the helper.

## Uninstall

```sh
sudo rm {helper_path}
```
"""
