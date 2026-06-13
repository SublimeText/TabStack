# TabStack Agent Notes

- This is a Sublime Text package, not a standalone app.
- Runtime target is Sublime Text's Python 3.14 plugin host.
- Root `main.py` is the only plugin entry file.
- `main.py` clears cached `plugin.*` modules before star-importing `plugin`, so keep exposed plugin symbols in `plugin/__init__.py`.
- Real implementation lives under `plugin/`.
- Per-window state is in-memory only, keyed by `window.id()` in `plugin/state.py`.
- `TabStackListener.on_activated` updates MRU order, but ignores activation during an active quick-panel session.
- `TabStackListener.on_close` removes closed views from all window stacks.
- Linux key bindings live in `Default (Linux).sublime-keymap`.
- The quick-panel session context key is `setting.tab_stack_quick_panel`.
- When that setting is `false`, `ctrl+tab`, `ctrl+shift+tab`, `ctrl+up`, and `ctrl+down` start `show_tab_stack`.
- When that setting is `true`, those keys call `tab_stack_move`, and `escape` or `ctrl+escape` call `tab_stack_cancel`.
- `plugin/linux_ctrl.py` uses X11/XWayland polling via `ctypes`; native Wayland without XWayland is unsupported.
- `show_tab_stack` starts a Ctrl-release poller and commits when Ctrl is released.
- Tab captions come from `plugin/captions.py`; views that are widgets, panels, or non-tab elements are excluded from the MRU list.
- Keep the MRU list per window and preserve the current preview behavior: preview must not reorder the stack.

## Verification

- `pyproject.toml` only defines `ruff` settings.
- Use `ruff check .` for linting.
- Use `ruff format .` for formatting.
- No repo-local test runner or task file is currently present.
