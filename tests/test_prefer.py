"""Golden / unit tests for catalog merge and newer-source pick (#1)."""

from __future__ import annotations

import unittest

from appgrid.backends.base import AppEntry
from appgrid.catalog.prefer import merge_by_newer, newer_source, pick_winner


def _entry(
    *,
    uid: str,
    backend: str,
    name: str,
    app_id: str = "",
    package: str = "",
    version: str = "",
    release_ts: int = 0,
    desktop_ids: list[str] | None = None,
    self_installed: bool = False,
) -> AppEntry:
    return AppEntry(
        uid=uid,
        backend=backend,
        app_id=app_id or uid,
        name=name,
        package=package,
        version=version,
        release_ts=release_ts,
        desktop_ids=list(desktop_ids or []),
        self_installed=self_installed,
        installed=self_installed,
    )


class PreferMergeTests(unittest.TestCase):
    def test_same_app_id_merges_to_one_card(self) -> None:
        apt = _entry(
            uid="apt:org.mozilla.firefox",
            backend="apt",
            name="Firefox",
            app_id="org.mozilla.firefox",
            package="firefox",
            version="131.0-1",
        )
        flatpak = _entry(
            uid="flatpak:org.mozilla.firefox",
            backend="flatpak",
            name="Firefox",
            app_id="org.mozilla.firefox",
            package="org.mozilla.firefox",
            version="133.0",
            release_ts=1_700_000_000,
        )
        merged = merge_by_newer([apt, flatpak])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].backend, "flatpak")
        self.assertEqual(merged[0].version, "133.0")
        self.assertEqual(len(merged[0].extras), 1)
        self.assertEqual(merged[0].extras[0].backend, "apt")

    def test_same_desktop_id_merges(self) -> None:
        apt = _entry(
            uid="apt:vlc",
            backend="apt",
            name="VLC media player",
            app_id="vlc",
            package="vlc",
            version="3.0.20-1",
            desktop_ids=["vlc.desktop"],
        )
        flatpak = _entry(
            uid="flatpak:org.videolan.VLC",
            backend="flatpak",
            name="VLC",
            app_id="org.videolan.VLC",
            package="org.videolan.VLC",
            version="3.0.21",
            desktop_ids=["vlc.desktop"],
            release_ts=1_700_000_100,
        )
        merged = merge_by_newer([apt, flatpak])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].backend, "flatpak")

    def test_name_only_near_miss_does_not_merge(self) -> None:
        """Same display name alone must not collapse unrelated packages into one card."""
        left = _entry(
            uid="apt:galculator",
            backend="apt",
            name="Calculator",
            app_id="galculator",
            package="galculator",
            version="2.1.4-1",
        )
        right = _entry(
            uid="flatpak:org.gnome.Calculator",
            backend="flatpak",
            name="Calculator",
            app_id="org.gnome.Calculator",
            package="org.gnome.Calculator",
            version="48.1",
        )
        merged = merge_by_newer([left, right])
        self.assertEqual(len(merged), 2)
        backends = {item.backend for item in merged}
        self.assertEqual(backends, {"apt", "flatpak"})

    def test_empty_version_never_wins(self) -> None:
        apt = _entry(
            uid="apt:gedit",
            backend="apt",
            name="Text Editor",
            app_id="org.gnome.gedit",
            package="gedit",
            version="",
        )
        flatpak = _entry(
            uid="flatpak:org.gnome.gedit",
            backend="flatpak",
            name="Text Editor",
            app_id="org.gnome.gedit",
            package="org.gnome.gedit",
            version="48.1",
        )
        winner = newer_source(apt, flatpak)
        self.assertIs(winner, flatpak)
        winner2 = newer_source(flatpak, apt)
        self.assertIs(winner2, flatpak)

    def test_one_sided_release_ts_preferred(self) -> None:
        apt = _entry(
            uid="apt:firefox",
            backend="apt",
            name="Firefox",
            app_id="org.mozilla.firefox",
            package="firefox",
            version="131.0-1",
            release_ts=0,
        )
        flatpak = _entry(
            uid="flatpak:org.mozilla.firefox",
            backend="flatpak",
            name="Firefox",
            app_id="org.mozilla.firefox",
            package="org.mozilla.firefox",
            version="133.0",
            release_ts=999,
        )
        self.assertIs(newer_source(apt, flatpak), flatpak)

    def test_no_ts_falls_back_to_version_compare(self) -> None:
        apt = _entry(
            uid="apt:app",
            backend="apt",
            name="App",
            app_id="org.example.app",
            package="app",
            version="1.0",
        )
        flatpak = _entry(
            uid="flatpak:org.example.app",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="3.2.1",
        )
        self.assertIs(newer_source(apt, flatpak), flatpak)

    def test_winner_keeps_own_version_when_older_copy_installed(self) -> None:
        apt = _entry(
            uid="apt:app",
            backend="apt",
            name="App",
            app_id="org.example.app",
            package="app",
            version="1.0",
            self_installed=True,
        )
        flatpak = _entry(
            uid="flatpak:org.example.app",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="9.0",
            release_ts=100,
        )
        winner = pick_winner([apt, flatpak])
        self.assertEqual(winner.backend, "flatpak")
        self.assertEqual(winner.version, "9.0")
        self.assertTrue(winner.installed)

    def test_simple_pkg_matches_flatpak_id_tail(self) -> None:
        apt = _entry(
            uid="apt:firefox",
            backend="apt",
            name="Firefox Web Browser",
            app_id="firefox",
            package="firefox",
            version="130",
        )
        flatpak = _entry(
            uid="flatpak:org.mozilla.firefox",
            backend="flatpak",
            name="Firefox",
            app_id="org.mozilla.firefox",
            package="org.mozilla.firefox",
            version="133",
            release_ts=50,
        )
        merged = merge_by_newer([apt, flatpak])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].backend, "flatpak")

    def test_one_sided_ts_yields_to_newer_version(self) -> None:
        """Lone release_ts must not beat a clearly newer version on the other side (#4)."""
        apt = _entry(
            uid="apt:app",
            backend="apt",
            name="App",
            app_id="org.example.app",
            package="app",
            version="2.0",
            release_ts=0,
        )
        flatpak = _entry(
            uid="flatpak:org.example.app",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="1.0",
            release_ts=1000,
        )
        self.assertIs(newer_source(apt, flatpak), apt)
        self.assertIs(newer_source(flatpak, apt), apt)

    def test_runtime_train_does_not_debian_beat_app_version(self) -> None:
        """Cross-backend: runtime-style 24.08.x must not Debian-rank over 1.2.0 (#8)."""
        apt = _entry(
            uid="apt:app",
            backend="apt",
            name="App",
            app_id="org.example.app",
            package="app",
            version="1.2.0-1",
        )
        flatpak = _entry(
            uid="flatpak:org.example.app",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="24.08.1",
        )
        # No comparable scheme → APT tie-break.
        self.assertIs(newer_source(apt, flatpak), apt)

    def test_one_sided_ts_runtime_train_yields_to_app_version(self) -> None:
        """One-sided release_ts must not keep a runtime train over a normal version (#6)."""
        apt = _entry(
            uid="apt:app",
            backend="apt",
            name="App",
            app_id="org.example.app",
            package="app",
            version="1.2.0-1",
            release_ts=0,
        )
        flatpak = _entry(
            uid="flatpak:org.example.app",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="24.08.1",
            release_ts=1,
        )
        self.assertIs(newer_source(apt, flatpak), apt)
        self.assertIs(newer_source(flatpak, apt), apt)

    def test_same_backend_equal_version_honors_one_sided_ts(self) -> None:
        """Equal versions: one-sided release_ts picks the stamped side (hunt-4 sev 3)."""
        older = _entry(
            uid="flatpak:a",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="1.0",
            release_ts=0,
        )
        newer = _entry(
            uid="flatpak:b",
            backend="flatpak",
            name="App",
            app_id="org.example.app",
            package="org.example.app",
            version="1.0",
            release_ts=99,
        )
        self.assertIs(newer_source(older, newer), newer)
        self.assertIs(newer_source(newer, older), newer)


if __name__ == "__main__":
    unittest.main()

