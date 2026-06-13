# TabStack

TabStack is a Sublime Text package for switching between open tabs using an MRU-style stack.
It keeps tab order per window and previews tabs in the quick panel before committing the switch.

## Installation

TabStack is not available on Package Control yet.
Install it manually with git:

```bash
git clone <repository-url> "${HOME}/.config/sublime-text/Packages/TabStack"
```

To update later, run `git pull` inside the `TabStack` directory
and restart Sublime Text.

## Usage

The default Linux key bindings are:

- `ctrl+tab`
- `ctrl+shift+tab`
- `ctrl+up`
- `ctrl+down`

Press one of those shortcuts to open the tab stack quick panel.
Use the same keys to move through the list while it is open.
Release `ctrl` to commit the selected tab.
Press `ctrl+escape` to cancel.

## Platform Support

TabStack currently supports **Linux only**.
It relies on X11 or XWayland to detect Ctrl release events.
Native Wayland support is unlikely to be possible.
