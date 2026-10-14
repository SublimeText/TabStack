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
It reads the native key state to detect modifier release events.

On Linux, TabStack uses the `tabstack-keystate` helper
whenever it is installed and works,
see [Wayland Setup](#wayland-setup).
Otherwise it falls back to the X11 key state API,
so Sublime must run under X11 or XWayland
(for example with `GDK_BACKEND=x11`).
Note that X11 detection has not been reported to work yet.
TabStack treats a session as native Wayland
when `WAYLAND_DISPLAY` is set and `GDK_BACKEND` is not `x11`,
so `GDK_BACKEND=x11` is also the way
to use X11 detection without the helper on a Wayland desktop.

A native Wayland session exposes no way to poll global key state
(a deliberate security restriction in the protocol),
and Sublime Text does not provide a key-release API to plugins.
See also the related [upstream issue][].
As a workaround,
TabStack ships the source of a small helper program, `tabstack-keystate`,
that reads the Ctrl key state from the kernel's input devices.
Native Wayland needs this helper,
see [Wayland Setup](#wayland-setup).


## Wayland Setup

The helper is not installed automatically.
You review its source,
then build and install it yourself.
TabStack never runs `sudo`, a compiler or `setcap`.

Run `TabStack: Set Up Ctrl Detection for Wayland` from the Command Palette.
It extracts the helper source,
opens it for review,
and shows the commands below.
When the first `ctrl+tab` on native Wayland finds no working helper,
TabStack also offers to show this setup once per plugin load.

In the directory the command extracted the source to,
build, install and grant the capability:

```sh
cc -std=c11 -O2 -Wall -Wextra -o tabstack-keystate tabstack-keystate.c
sudo install -D -o root -g root -m 0755 tabstack-keystate /usr/local/libexec/tabstack-keystate
sudo setcap cap_dac_read_search=ep /usr/local/libexec/tabstack-keystate
```

Then run the setup command again to verify that the helper works.

To uninstall:

```sh
sudo rm /usr/local/libexec/tabstack-keystate
```

After a package update,
the setup command may report an outdated helper.
In that case, build and install it again with the commands above.

### Settings

In `TabStack.sublime-settings`,
which `Preferences: TabStack Settings` opens from the Command Palette:

- `keystate_helper_path`:
  the path of the installed helper,
  `/usr/local/libexec/tabstack-keystate` by default.
- `keystate_ctrl_keys`:
  the keys the helper treats as Ctrl,
  `["leftctrl", "rightctrl"]` by default.
  The helper reads physical keys
  and does not see the keyboard layout,
  so set this if your layout remaps Ctrl,
  for example `["leftctrl", "rightctrl", "capslock"]` for the XKB option `ctrl:nocaps`,
  or `["capslock", "rightctrl"]` for `ctrl:swapcaps`.
  Allowed are `leftctrl`, `rightctrl`, `capslock`,
  `leftalt`, `rightalt`, `leftmeta`, `rightmeta` and `compose`.
- `show_wayland_setup_dialog`:
  set to `false` to suppress the dialog
  that offers the setup on native Wayland.
  The dialog's "Don't Ask Again" button sets it for you.

### Security Notes

- Reading `/dev/input/event*` requires privileges.
  The helper gets them through the file capability `cap_dac_read_search`,
  which allows reading any file regardless of permissions.
- The helper sets `no_new_privs` at startup,
  opens every `/dev/input/event*` device read-only
  and keeps only those that advertise one of the watched keys.
  It then drops all capabilities immediately,
  before it reports any state.
  Review the source to confirm this.
- Anyone who can execute the helper can run it,
  so any local user can read the Ctrl state of your keyboards through it.
  It reports nothing but whether one of the watched keys is held,
  and it only accepts the modifier keys listed under `keystate_ctrl_keys`,
  so it cannot be used to log typed characters.
- Installing it as `root:root` with mode `0755` in `/usr/local/libexec`
  prevents the user's own processes from modifying it.
  Replacing the binary drops the capability,
  so grant it again after every rebuild.
- An alternative is to add your user to the `input` group
  and skip the capability.
  Note that this typically gives every process of your user
  read-write access to all input event devices (keyboards and mice),
  allowing it to read all keystrokes including passwords,
  inject events and grab devices.

### Limitations

Flatpak and Snap builds of Sublime Text are not supported.
Their sandbox or `no_new_privs` setting
makes the kernel ignore file capabilities when running the helper.


## Caveats

Support for sheets that are not backed by text,
i.e. HTML sheets and image sheets,
cannot properly be monitored before ST build 4205
due to missing API support.


[Sublime Text]: https://www.sublimetext.com/
[Video Showcase]: https://raw.githubusercontent.com/SublimeText/TabStack/refs/heads/main/media/showcase.mp4
[Package Control]: https://packages.sublimetext.com/
[upstream issue]: https://github.com/sublimehq/sublime_text/issues/6931
