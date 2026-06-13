# TabStack Agent Notes

- This is a Sublime Text package, not a standalone app.
- Runtime target is Sublime Text's Python 3.14 plugin host.
- Root `main.py` is the only plugin entry file.
- `main.py` clears cached `plugin.*` modules before star-importing `plugin`, so keep exposed plugin symbols in `plugin/__init__.py`.
- Real implementation lives under `plugin/`.
- Modifier-release detection lives in `plugin/ctrl_release/`.
- Per-window state is in-memory only, keyed by `window.id()` in `plugin/state.py`.
- `TabStackListener.on_activated` updates MRU order, but ignores activation during an active quick-panel session.
- `TabStackListener.on_close` removes closed views from all window stacks.
- Key bindings are shared among all platforms and live in `Default.sublime-keymap`.
- The quick-panel session context key is `setting.tab_stack_quick_panel`.
- When that setting is `false`, `ctrl+tab`, `ctrl+shift+tab`, `ctrl+up`, and `ctrl+down` start `show_tab_stack`.
- When that setting is `true`, those keys call `tab_stack_move`, and `escape` or `ctrl+escape` call `tab_stack_cancel`.
- `plugin/ctrl_release/linux.py` uses X11/XWayland polling via `ctypes`; native Wayland without XWayland is unsupported.
- `plugin/ctrl_release/windows.py` uses `GetAsyncKeyState` polling via `ctypes`.
- `plugin/ctrl_release/macos.py` uses CoreGraphics polling via `ctypes`.
- `show_tab_stack` starts a Ctrl-release poller and commits when Ctrl is released.
- Tab captions come from `plugin/captions.py`; views that are widgets, panels, or non-tab elements are excluded from the MRU list.
- Keep the MRU list per window and preserve the current preview behavior: preview must not reorder the stack.

## Verification

- Run dev tools with `uv run`, for example `uv run ruff check .` and `uv run ruff format .`.
- `pyproject.toml` only defines `ruff` settings.
- Use `ruff check .` for linting via `uv run`.
- Use `ruff format .` for formatting via `uv run`.
- No repo-local test runner or task file is currently present.
