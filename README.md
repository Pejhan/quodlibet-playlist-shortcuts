# Add the current track to playlists with global shortcuts

A community plugin that adds the current track to a chosen playlist through
a global shortcut. Tracks can belong to multiple playlists; repeated presses
never duplicate or remove a track.

## Install and configure

Download this repository, then run from its root:

```sh
mkdir -p ~/.config/quodlibet/plugins
install -m 644 playlist_shortcuts.py ~/.config/quodlibet/plugins/
```

Open Quod Libet's Plugins window, click **Refresh** (or restart Quod Libet),
and enable **Add Current Track to Playlist**.
Its preferences list your playlists with a shortcut field beside each name.
Enter a combination such as `Ctrl+Alt+1` or `Meta+Shift+F1`, then click
**Apply**. **Clear** clears only the shortcut. No shortcuts are assigned
by default. Shortcut editing requires KDE Plasma, including on Wayland.

Pressing a shortcut appends the current track to that playlist and saves it.
If the track is already present, nothing changes. Different shortcuts can add
the same track to several playlists. This plugin never removes tracks.
It also works while playback is paused; an empty player or a track that
cannot be added to playlists is ignored.

Quod Libet must be running with the plugin enabled. KDE remembers bindings
across restarts; disabling the plugin stops additions but retains shortcuts.
Existing shortcut conflicts are reported beside the playlist.

Bindings are associated with playlist names. Clear a playlist's shortcut
before renaming or deleting it, then assign the desired shortcut to the new
name. The preferences list follows playlist additions, deletions, and renames.

This plugin uses the `app.library.playlists` API available in Quod Libet 4.7.1
and the development version used for these tests. Older installations without that API are not
supported. No separate desktop file needs to be installed.

## Uninstall

Clear each assigned shortcut in the plugin preferences, then disable the
plugin. Remove `playlist_shortcuts.py` from your Quod Libet user plugins
directory and refresh the Plugins window or restart Quod Libet. Generated
KDE action files are named `quodlibet-playlist-<identifier>.desktop` under
`~/.local/share/kglobalaccel/`; these can also be removed after clearing the
bindings.

If you set `XDG_CONFIG_HOME` or `XDG_DATA_HOME`, use the corresponding
Quod Libet plugins and kglobalaccel directories instead of the default paths
shown above.

## Requirements

- Linux with Quod Libet 4.7.1. Other versions have not been verified here.
- KDE Plasma for configuring global shortcuts inside the plugin.
- Python D-Bus bindings (`dbus-python`) and the `gdbus` command from GLib.
- Quod Libet's usual Python and GTK dependencies.

These instructions target a normal desktop installation. Flatpak and Snap
installations have not been tested.

## Development and tests

The regression tests use Quod Libet's own test helpers, so a Quod Libet source
checkout with its `tests/` directory and test dependencies is required.
The plugin module under test is loaded from **this repository**.

From this repository's root:

```sh
QUODLIBET_SOURCE_DIR=/path/to/quodlibet python3 -m pytest
```

Run in a graphical session with D-Bus available. For headless testing, install
Xvfb and `pyvirtualdisplay`, which Quod Libet's test helpers can use. The helpers
isolate test user data and start a separate D-Bus session. Shortcut-service
calls are mocked; the tests do not assign real desktop shortcuts.

## License

GPL-2.0-or-later. See [COPYING](COPYING). This is an independent community
plugin for [Quod Libet](https://github.com/quodlibet/quodlibet).
