# <img src="assets/favorite.svg" width="32" height="32" alt=""> Playlist Shortcuts

Add the current Quod Libet track to playlists with global keyboard shortcuts.
Tracks can belong to multiple playlists; repeated presses never duplicate or remove them.

## Requirements

Linux, Quod Libet 4.7.1 (other versions unverified), KDE Plasma,
`dbus-python`, and GLib’s `gdbus`. Wayland is supported; Flatpak and Snap are untested.

## Install and configure

From this repository’s root:

```sh
mkdir -p ~/.config/quodlibet/plugins
install -m 644 playlist_shortcuts.py ~/.config/quodlibet/plugins/
```

1. Open Quod Libet’s **Plugins**, click **Refresh** (or restart), and enable **Add Current Track to Playlist**.
2. In its preferences, enter a shortcut beside a playlist, such as `Ctrl+Alt+1`, and click **Apply**. Conflicts appear beside the playlist; **Clear** removes a binding.
3. Keep Quod Libet running and press the shortcut to add the current track, even while paused.

Bindings survive restarts and disabling the plugin. Clear a playlist’s shortcut
before renaming or deleting it, then assign a new binding if needed.

## Uninstall

Clear the bindings in preferences, disable the plugin, and remove
`~/.config/quodlibet/plugins/playlist_shortcuts.py`. After clearing bindings,
you can also remove its `quodlibet-playlist-*.desktop` files from
`~/.local/share/kglobalaccel/`.

Use your `XDG_CONFIG_HOME` and `XDG_DATA_HOME` paths if customized.

## Tests

With a Quod Libet source checkout and its test dependencies installed:

```sh
QUODLIBET_SOURCE_DIR=/path/to/quodlibet python3 -m pytest
```

Run in a graphical D-Bus session; headless testing requires Xvfb and
`pyvirtualdisplay`. Tests use isolated data and mock shortcut registration.

## License

[GPL-2.0-or-later](COPYING). An independent community plugin for
[Quod Libet](https://github.com/quodlibet/quodlibet).
[Favorite icon](assets/README.md) from KDE Breeze, LGPL-3.0-or-later.
