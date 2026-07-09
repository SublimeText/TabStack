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
- Uner Linux, Ctrl-release polling uses the X11 key state API, so Sublime must run under X11 or XWayland; a native Wayland session has no pollable global key state and Sublime exposes no key-release API.
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
- `pyproject.toml` only defines Ruff settings; there is no repo-local test runner.
