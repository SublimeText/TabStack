# TabStack Agent Notes

## Entry Points

- This is a Sublime Text package, not a standalone app.
- Runtime target is Sublime Text's Python 3.14 plugin host.
- `main.py` is the only entry file; it clears cached `plugin.*` modules before star-importing `plugin`.
- Keep exported plugin symbols in `plugin/__init__.py`; implementation lives under `plugin/`.

## Behavior

- State is in-memory per window, keyed by `window.id()` in `plugin/state.py`.
- MRU order is per window.
- `TabStackListener.on_activated` updates history unless a quick-panel session is active.
- `TabStackListener.on_close` prunes closed sheets and removes empty window state.
- Tab captions come from `plugin/captions.py`; widgets, panels, and transient/non-tab views are excluded from MRU.
- Ctrl-release detection lives in `plugin/ctrl_release/`.
- Under Linux, Ctrl-release detection uses the `tabstack-keystate` helper (`plugin/ctrl_release/linux/keystate_helper.py`) when its probe succeeds.
  `plugin_loaded` probes it on the async thread, because running it can take up to 2 s; until the result arrives, Linux behaves as if the helper were missing, but without the setup dialog.
  The probe records the helper path and the `keystate_ctrl_keys` it ran with, the poller runs exactly that command, and a change of either setting triggers a new probe.
  The helper only accepts the modifier names in its `allowed_keys` table as arguments, so that it cannot serve as a keylogger; keep it that way.
  A helper that fails during a session (spawn error, bad handshake, `error` line, early EOF) still commits that session, but triggers a new probe unless a newer one has superseded it.
  The helper reads evdev key state with `cap_dac_read_search`, is spawned once per session, and reports Ctrl state changes on stdout.
- Without a working helper, Linux falls back to the X11 key state API (`plugin/ctrl_release/linux/x11.py`), but not on native Wayland (`is_native_wayland()` in `plugin/ctrl_release/linux/__init__.py`), because XWayland reports Ctrl as released while a Wayland client has focus; Sublime exposes no key-release API.
- On native Wayland without a working helper, the first `ctrl+tab` per plugin load shows a dialog offering the setup (`offer_wayland_setup` in `plugin/setup.py`), unless `show_wayland_setup_dialog` is `false`.
- `tab_stack_setup_keystate_helper` (Command Palette: `TabStack: Set Up Ctrl Detection for Wayland`) re-probes, extracts `keystate/tabstack-keystate.c` to `sublime.cache_path()/TabStack/keystate/`, and shows the build, install and `setcap` commands.
  It reuses an open instructions view (marked by the `tab_stack_setup_instructions` view setting) and selects it together with the source, instructions on the left.
  The plugin never runs `sudo`, a compiler or `setcap`; the user installs the helper to `keystate_helper_path` (default `/usr/local/libexec/tabstack-keystate`) with `cap_dac_read_search`, which the helper drops right after opening the input devices.
- `tab_stack_open` arms a pending session, starts a Ctrl-release poller, and opens the quick panel after a short delay unless Ctrl is released first.
- Wrap-around cycling is implemented by intentionally closing and reopening the quick panel at the opposite boundary.
  That handoff keeps the session active and reuses the existing Ctrl-release poller.
- `tab_stack.session_active` is the quick-panel session context key.
- `tab_stack.session_pending` is the arming context before the panel appears.
- Boundary-only contexts are `tab_stack.quick_panel_at_top` and `tab_stack.quick_panel_at_bottom`.
- When `tab_stack.session_active` is `false`, `ctrl+tab` starts `tab_stack_open`.
  `ctrl+shift+tab` is bound as a no-op to prevent accidental presses.
- When `tab_stack.session_active` is `true`, non-boundary `ctrl+tab`, `ctrl+shift+tab`, `ctrl+up`, and `ctrl+down` call `move`, boundary presses call `tab_stack_cycle`, and `ctrl+escape` calls `tab_stack_cancel`.

## Verification

- Use `uv run ruff check .` for linting.
- Use `uv run ruff format .` for formatting.
- Use `uv run basedpyright` for type checks.
- `pyproject.toml` only defines Ruff settings; there is no test runner for the plugin.
- The helper builds with `cc -std=c11 -O2 -Wall -Wextra -Werror -o <scratch>/tabstack-keystate keystate/tabstack-keystate.c`.
- `tests/keystate_smoke.py` tests the helper against a virtual uinput keyboard; it needs root and `/dev/uinput` and runs in CI (`tests/` is export-ignored).
