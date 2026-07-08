# TabStack

TabStack is a [Sublime Text][] (build 4100+) package
for switching between open tabs using an MRU-style stack.
It keeps tab order per window
and previews tabs in the quick panel
before committing the switch.
It also preserves tab ordering across sessions
and supports multiple selections.
When closing a tab,
TabStack restores the previous selection.

[Video Showcase][]


## Installation

TabStack is available on [Package Control][].
Open the Command Palette,
select `Package Control: Install Package`
and find "TabStack" in the list.


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

On Linux, detection uses the X11 key state API,
so Sublime must run under X11 or XWayland
(for example with `GDK_BACKEND=x11`).
Note that this has not been reported to work yet.

A native Wayland session exposes no way to poll global key state
(a deliberate security restriction in the protocol),
and Sublime Text does not provide a key-release API to plugins.
See also the related [upstream issue][]

[Sublime Text]: https://www.sublimetext.com/
[Video Showcase]: https://raw.githubusercontent.com/FichteFoll/TabStack/refs/heads/main/media/showcase.mp4
[Package Control]: https://packages.sublimetext.com/
[upstream issue]: https://github.com/sublimehq/sublime_text/issues/6931
