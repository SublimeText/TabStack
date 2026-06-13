# TabStack

TabStack is a [Sublime Text][] (build 4205+) package
for switching between open tabs using an MRU-style stack.
It keeps tab order per window
and previews tabs in the quick panel
before committing the switch.
It also preserves tab ordering across sessions
by storing each view's last activation time.

<video controls muted playsinline loop>
  <source src="./media/showcase.mp4" type="video/mp4">
</video>

## Installation

TabStack is not available on Package Control yet.
To install it manually with git,
first locate your Packages folder (*Preferences > Browse Packages...*)
and then clone the repository into that folder:

```bash
git clone https://github.com/FichteFoll/TabStack
```

To update later, run `git pull` inside the `TabStack` directory
and restart Sublime Text.

## Usage

The key bindings are:

- `ctrl+tab`
- `ctrl+shift+tab`
- `ctrl+up`
- `ctrl+down`

These are not configurable
because the release detection of the `ctrl` key is hard-coded.

Press one of those shortcuts to open the tab stack quick panel.
Use the same keys to move through the list while it is open.
Release `ctrl` to commit the selected tab.
Press `ctrl+escape` to cancel.

## Platform Support

TabStack supports **Linux, Windows, and macOS**.
It polls the native key state APIs to detect modifier release events.

Linux relies on X11 or XWayland.
Native Wayland support is unlikely to be possible
due to security restrictions in the protocol.

[Sublime Text]: https://www.sublimetext.com/
