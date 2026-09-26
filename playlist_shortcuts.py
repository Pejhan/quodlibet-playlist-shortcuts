# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""Add the current track to playlists through per-playlist global shortcuts.

Kept self-contained so it can also be installed as a user plugin. The KDE
shortcut editor follows the same protocol as Trash Current Track.
"""

import hashlib
from pathlib import Path

import dbus
import dbus.service
from gi.repository import GLib, Gtk

from quodlibet import _, app, print_w
from quodlibet.plugins.events import EventPlugin


BUS_NAME = "io.github.quodlibet.AddCurrentToPlaylist"
OBJECT_PATH = "/io/github/quodlibet/AddCurrentToPlaylist"


def playlist_token(name):
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


# Qt key values used by KDE's shortcut service. Printable keys use Unicode.
_KEYS = {
    "Escape": 0x01000000,
    "Tab": 0x01000001,
    "Backspace": 0x01000003,
    "Return": 0x01000004,
    "Enter": 0x01000005,
    "Insert": 0x01000006,
    "Delete": 0x01000007,
    "Pause": 0x01000008,
    "Print": 0x01000009,
    "Home": 0x01000010,
    "End": 0x01000011,
    "Left": 0x01000012,
    "Up": 0x01000013,
    "Right": 0x01000014,
    "Down": 0x01000015,
    "PageUp": 0x01000016,
    "PageDown": 0x01000017,
    "Space": 0x20,
    "Plus": 0x2B,
}
_KEYS.update({f"F{i}": 0x01000030 + i - 1 for i in range(1, 36)})
_MODIFIERS = {
    "Meta": 0x10000000,
    "Ctrl": 0x04000000,
    "Alt": 0x08000000,
    "Shift": 0x02000000,
}


def parse_shortcut(text):
    """Convert a single user-entered key combination to a Qt key value."""
    if not text.strip():
        return 0
    parts = [part.strip().lower() for part in text.split("+")]
    modifiers = {name.lower(): value for name, value in _MODIFIERS.items()}
    modifiers.update(super=_MODIFIERS["Meta"], control=_MODIFIERS["Ctrl"])
    result = 0
    for part in parts[:-1]:
        if part not in modifiers or result & modifiers[part]:
            raise ValueError(
                _("Use a shortcut such as Meta+Shift+Delete or Ctrl+Alt+T.")
            )
        result |= modifiers[part]
    key = parts[-1]
    key = {
        "del": "delete",
        "esc": "escape",
        "pgup": "pageup",
        "pgdown": "pagedown",
    }.get(key, key)
    named = {name.lower(): value for name, value in _KEYS.items()}
    if key in named:
        return result | named[key]
    if len(key) == 1 and key.isprintable() and len(key.upper()) == 1:
        return result | ord(key.upper())
    raise ValueError(
        _("Enter a letter, number, function key, or a key such as Delete.")
    )


def format_shortcut(value):
    if not value:
        return ""
    modifiers = [name for name, mask in _MODIFIERS.items() if value & mask]
    key = value & 0x01FFFFFF
    names = {code: name for name, code in _KEYS.items()}
    if key in names:
        name = names[key]
    elif 0x20 <= key <= 0x10FFFF and chr(key).isprintable():
        name = chr(key)
    else:
        raise ValueError(
            _("This shortcut cannot be edited here. Choose a new shortcut.")
        )
    if value & ~0x1FFFFFFF:
        raise ValueError(
            _("This shortcut cannot be edited here. Choose a new shortcut.")
        )
    return "+".join(modifiers + [name])


class KDEShortcut:
    """Manage the desktop's persistent binding, preserving existing choices."""

    def __init__(self, name):
        self.token = playlist_token(name)
        self.component = f"quodlibet-playlist-{self.token}.desktop"
        self.action = [self.component, "_launch", "Quod Libet: Add to Playlist", name]
        bus = dbus.SessionBus()
        if not bus.name_has_owner("org.kde.kglobalaccel"):
            raise ValueError(_("Shortcut editing here requires KDE Plasma."))
        self._api = dbus.Interface(
            bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"),
            "org.kde.KGlobalAccel",
        )
        self._install_action()
        self._api.doRegister(self.action)
        # SetPresent, with autoloading: keep a saved binding, or leave it unset.
        self._api.setShortcut(
            self.action, dbus.Array([], signature="i"), dbus.UInt32(2)
        )

    def _install_action(self):
        path = Path(GLib.get_user_data_dir()) / "kglobalaccel" / self.component
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only a hexadecimal identifier enters Exec, never a playlist name.
        command = (
            f"gdbus call --session --dest {BUS_NAME} --object-path {OBJECT_PATH} "
            f"--method {BUS_NAME}.AddCurrent {self.token}"
        )
        with path.open("x", encoding="utf-8") as output:
            output.write(
                "[Desktop Entry]\nType=Application\n"
                "Name=Quod Libet: Add to Playlist\nIcon=favorite\n"
                f"Exec={command}\nTerminal=false\nStartupNotify=false\n"
                "X-KDE-GlobalAccel-CommandShortcut=true\n"
            )

    def get(self):
        return list(self._api.shortcut(self.action))

    def set(self, key):
        previous = self.get()
        if (
            key
            and key not in previous
            and not self._api.isGlobalShortcutAvailable(key, "")
        ):
            raise ValueError(_("That shortcut is already in use. Choose another one."))
        requested = [key] if key else []
        # SetPresent | NoAutoloading: persist this explicit user choice.
        actual = list(
            self._api.setShortcut(
                self.action, dbus.Array(requested, signature="i"), dbus.UInt32(6)
            )
        )
        if actual != requested:
            self._api.setShortcut(
                self.action, dbus.Array(previous, signature="i"), dbus.UInt32(6)
            )
            raise ValueError(
                _("The shortcut could not be assigned. Choose another one.")
            )


class PlaylistShortcutRow(Gtk.Box):
    def __init__(self, playlist):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._backend = None
        row = Gtk.Box(spacing=6)
        name = Gtk.Label(label=playlist.name, xalign=0)
        name.set_line_wrap(True)
        name.set_width_chars(20)
        name.set_max_width_chars(25)
        row.pack_start(name, True, True, 0)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(_("Not set"))
        self.entry.set_tooltip_text(
            _("For example: Ctrl+Alt+1 or Meta+Shift+F1. Meta is the Windows key.")
        )
        self.apply_button = Gtk.Button(label=_("Apply"))
        self.clear_button = Gtk.Button(label=_("Clear"))
        row.pack_start(self.entry, False, False, 0)
        row.pack_start(self.apply_button, False, False, 0)
        row.pack_start(self.clear_button, False, False, 0)
        self.pack_start(row, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(70)
        self.pack_start(self.status, False, False, 0)
        self.apply_button.connect("clicked", lambda *_: self._save())
        self.entry.connect("activate", lambda *_: self._save())
        self.clear_button.connect("clicked", lambda *_: self._save(""))
        try:
            self._backend = KDEShortcut(playlist.name)
            keys = self._backend.get()
            self.entry.set_text(format_shortcut(keys[0]) if keys else "")
        except (dbus.DBusException, OSError, ValueError) as error:
            self._show_error(error)
            if self._backend is None:
                row.set_sensitive(False)

    def _show_error(self, error):
        if isinstance(error, ValueError):
            message = str(error)
        else:
            print_w(f"Could not configure playlist shortcut: {error}")
            message = _("Could not configure the global shortcut. Please try again.")
        self.status.set_text(message)

    def _save(self, text=None):
        try:
            key = parse_shortcut(self.entry.get_text() if text is None else text)
            self._backend.set(key)
        except (dbus.DBusException, OSError, ValueError) as error:
            self._show_error(error)
        else:
            self.entry.set_text(format_shortcut(key))
            self.status.set_text(
                _("Shortcut saved.") if key else _("Shortcut cleared.")
            )


class ShortcutPreferences(Gtk.Box):
    def __init__(self, playlists):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._playlists = playlists
        self._names = None
        self._signals = []
        description = Gtk.Label(
            label=_(
                "Choose a global shortcut beside each playlist, then click Apply. "
                "Tracks already in a playlist are left unchanged. "
                "Clear removes only the shortcut."
            ),
            xalign=0,
        )
        description.set_line_wrap(True)
        description.set_max_width_chars(70)
        self.pack_start(description, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(240)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.add(self.rows)
        self.pack_start(scroll, True, True, 0)
        for signal in ("added", "removed", "changed"):
            self._signals.append(playlists.connect(signal, self._refresh))
        self.connect("destroy", self._destroy)
        self._refresh()
        self.show_all()

    def _refresh(self, *args):
        playlists = sorted(self._playlists, key=lambda p: p.name.casefold())
        names = [playlist.name for playlist in playlists]
        # Song changes also emit "changed"; preserve any edits in progress.
        if names == self._names:
            return
        self._names = names
        for child in self.rows.get_children():
            child.destroy()
        if not playlists:
            self.rows.pack_start(
                Gtk.Label(label=_("Create a playlist to assign a shortcut."), xalign=0),
                False,
                False,
                0,
            )
        for playlist in playlists:
            self.rows.pack_start(PlaylistShortcutRow(playlist), False, False, 0)
        self.rows.show_all()

    def _destroy(self, *args):
        for signal in self._signals:
            self._playlists.disconnect(signal)
        self._signals = []


class PlaylistShortcutService(dbus.service.Object):
    def __init__(self):
        self._bus_name = dbus.service.BusName(
            BUS_NAME, bus=dbus.SessionBus(), do_not_queue=True
        )
        super().__init__(self._bus_name, OBJECT_PATH)

    @dbus.service.method(BUS_NAME, in_signature="s", out_signature="b")
    def AddCurrent(self, token):
        song = app.player.song if app.player else None
        if song is None or not song.can_add or app.library is None:
            return False
        playlist = next(
            (p for p in app.library.playlists if playlist_token(p.name) == token),
            None,
        )
        if playlist is None or song in playlist or song("~filename") in playlist:
            return False
        # D-Bus dispatches on the GTK main loop. Complete this request before
        # returning so repeats see the new membership immediately.
        playlist.append(song)
        playlist.write()
        return True

    def close(self):
        self.remove_from_connection()
        self._bus_name = None


class PlaylistShortcutsPlugin(EventPlugin):
    PLUGIN_ID = "playlist_shortcuts"
    PLUGIN_NAME = _("Add Current Track to Playlist")
    PLUGIN_DESC = _("Add the current track to playlists using global shortcuts. ")
    PLUGIN_ICON = "favorite"

    def PluginPreferences(self, parent):
        return ShortcutPreferences(app.library.playlists)

    def enabled(self):
        self._service = PlaylistShortcutService()

    def disabled(self):
        self._service.close()
        self._service = None
