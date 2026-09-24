# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("dbus")
if sys.platform != "linux":
    pytest.skip("Playlist shortcuts require Linux", allow_module_level=True)

from quodlibet import config
import playlist_shortcuts as plugin
from quodlibet.formats import AudioFile
from quodlibet.library import SongFileLibrary
from quodlibet.library.playlist import PlaylistLibrary
from quodlibet.util.collection import XSPFBackedPlaylist
from tests import TestCase, mkdtemp


class TPlaylistShortcuts(TestCase):
    def setUp(self):
        config.init()
        self.library = SongFileLibrary()
        self.song = AudioFile({"~filename": "/example/song.ogg"})
        self.song.sanitize()
        self.library.add([self.song])
        self.playlists = PlaylistLibrary(self.library, mkdtemp())
        self.playlist = self.playlists.create("Favorites")
        self.app = SimpleNamespace(
            player=SimpleNamespace(song=self.song),
            library=SimpleNamespace(playlists=self.playlists),
        )
        self.app_patch = patch.object(plugin, "app", self.app)
        self.app_patch.start()
        self.service = plugin.PlaylistShortcutService()

    def tearDown(self):
        self.service.close()
        self.app_patch.stop()
        self.playlists.destroy()
        self.library.destroy()
        config.quit()

    def add(self, playlist=None):
        if playlist is None:
            playlist = self.playlist
        return self.service.AddCurrent(plugin.playlist_token(playlist.name))

    def test_add_saves_and_notifies(self):
        changed = Mock()
        self.playlists.connect("changed", changed)
        assert self.add()
        assert list(self.playlist) == [self.song]
        changed.assert_called()
        restored = XSPFBackedPlaylist(
            self.playlist.dir,
            Path(self.playlist.path).name,
            songs_lib=self.library,
        )
        assert list(restored) == [self.song]

    def test_repeated_shortcut_does_nothing(self):
        assert self.add()
        changed = Mock()
        self.playlists.connect("changed", changed)
        with patch.object(self.playlist, "write") as write:
            assert not self.add()
            assert not self.add()
        assert list(self.playlist) == [self.song]
        write.assert_not_called()
        changed.assert_not_called()

    def test_existing_track_is_not_removed(self):
        self.playlist.extend([self.song, self.song])
        assert not self.add()
        assert list(self.playlist) == [self.song, self.song]

    def test_same_track_can_belong_to_multiple_playlists(self):
        other = self.playlists.create("Driving")
        assert self.add()
        assert self.add(other)
        assert list(other) == list(self.playlist) == [self.song]

    def test_adds_current_track_in_order(self):
        assert self.add()
        following = AudioFile({"~filename": "/example/next.ogg"})
        self.app.player.song = following
        assert self.add()
        assert list(self.playlist) == [self.song, following]

    def test_no_player_or_current_track(self):
        self.app.player.song = None
        assert not self.add()
        self.app.player = None
        assert not self.add()
        assert not list(self.playlist)

    def test_track_that_cannot_be_added(self):
        self.app.player.song = Mock(can_add=False)
        assert not self.add()
        assert not list(self.playlist)

    def test_unknown_or_deleted_playlist(self):
        assert not self.service.AddCurrent("unknown")
        self.playlist.delete()
        assert not self.add()

    def test_masked_filename_is_already_a_member(self):
        self.playlist._list.append(self.song("~filename"))
        assert not self.add()
        assert len(self.playlist) == 1

    def test_reenable_releases_bus_name_and_object(self):
        self.service.close()
        self.service = plugin.PlaylistShortcutService()
        assert self.add()


class TPlaylistShortcutPreferences(TestCase):
    def setUp(self):
        self.keys = {}
        self.api = Mock()
        self.api.shortcut.side_effect = lambda action: self.keys.get(action[0], [])
        self.api.isGlobalShortcutAvailable.side_effect = lambda key, component: all(
            key not in keys for keys in self.keys.values()
        )

        def set_shortcut(action, keys, flags):
            if flags & 4:
                self.keys[action[0]] = list(keys)
            return self.keys.get(action[0], [])

        self.api.setShortcut.side_effect = set_shortcut
        self.interface_patch = patch.object(
            plugin.dbus, "Interface", return_value=self.api
        )
        self.bus_patch = patch.object(plugin.dbus, "SessionBus")
        self.data_dir = Path(mkdtemp())
        self.data_patch = patch.object(
            plugin.GLib, "get_user_data_dir", return_value=str(self.data_dir)
        )
        self.interface_patch.start()
        self.bus = self.bus_patch.start().return_value
        self.bus.name_has_owner.return_value = True
        self.data_patch.start()

    def tearDown(self):
        self.data_patch.stop()
        self.bus_patch.stop()
        self.interface_patch.stop()

    def test_independent_bindings_and_conflicts(self):
        first = plugin.KDEShortcut("Favorites")
        second = plugin.KDEShortcut("Driving")
        key = plugin.parse_shortcut("Ctrl+Alt+1")
        first.set(key)
        assert second.get() == []
        with self.assertRaises(ValueError):
            second.set(key)
        first.set(key)
        assert first.get() == [key]
        first.set(0)
        second.set(key)
        assert second.get() == [key]

    def test_reopening_preserves_shortcut(self):
        plugin.KDEShortcut("Favorites").set(plugin.parse_shortcut("Meta+F1"))
        assert plugin.KDEShortcut("Favorites").get() == [0x11000030]
        assert self.api.setShortcut.call_args.args[2] == 2

    def test_rejected_assignment_restores_binding(self):
        backend = plugin.KDEShortcut("Favorites")
        backend.set(plugin.parse_shortcut("Ctrl+1"))
        original = self.api.setShortcut.side_effect
        calls = 0

        def reject_first(action, keys, flags):
            nonlocal calls
            calls += 1
            return original(action, [] if calls == 1 else keys, flags)

        self.api.setShortcut.side_effect = reject_first
        with self.assertRaises(ValueError):
            backend.set(plugin.parse_shortcut("Ctrl+2"))
        assert backend.get() == [plugin.parse_shortcut("Ctrl+1")]

    def test_playlist_names_cannot_change_desktop_command(self):
        name = 'Music "quotes" %u \\ $HOME\nExec=bad / فارسی'
        backend = plugin.KDEShortcut(name)
        path = self.data_dir / "kglobalaccel" / backend.component
        contents = path.read_text()
        assert name not in contents
        assert f".AddCurrent {plugin.playlist_token(name)}\n" in contents
        assert "X-KDE-Shortcuts=" not in contents
        path.write_text("Existing customized action")
        plugin.KDEShortcut(name)
        assert path.read_text() == "Existing customized action"

    def test_row_apply_clear_and_invalid_input(self):
        row = plugin.PlaylistShortcutRow(SimpleNamespace(name="Favorites"))
        try:
            row.entry.set_text("Ctrl+Alt+1")
            row.apply_button.clicked()
            assert row._backend.get() == [plugin.parse_shortcut("Ctrl+Alt+1")]
            row.entry.set_text("invalid")
            row.apply_button.clicked()
            assert row._backend.get() == [plugin.parse_shortcut("Ctrl+Alt+1")]
            row.clear_button.clicked()
            assert row._backend.get() == []
            assert row.entry.get_text() == ""
        finally:
            row.destroy()

    def test_no_kde_disables_editor(self):
        self.bus.name_has_owner.return_value = False
        row = plugin.PlaylistShortcutRow(SimpleNamespace(name="Favorites"))
        try:
            assert not row.entry.is_sensitive()
            assert "requires KDE Plasma" in row.status.get_text()
            self.api.setShortcut.assert_not_called()
        finally:
            row.destroy()

    def test_preferences_follow_playlist_changes(self):
        config.init()
        library = SongFileLibrary()
        playlists = PlaylistLibrary(library, mkdtemp())
        prefs = plugin.ShortcutPreferences(playlists)
        try:
            assert "Create a playlist" in prefs.rows.get_children()[0].get_text()
            playlist = playlists.create("Favorites")
            row = prefs.rows.get_children()[0]
            row.entry.set_text("Ctrl+Alt+1")
            playlists.changed([playlist])
            assert prefs.rows.get_children()[0] is row
            assert row.entry.get_text() == "Ctrl+Alt+1"
            playlist.rename("Driving")
            assert prefs._names == ["Driving"]
            playlist.delete()
            assert prefs._names == []
            prefs.destroy()
            assert prefs._signals == []
        finally:
            prefs.destroy()
            playlists.destroy()
            library.destroy()
            config.quit()
