"""Unit tests for privileged helper package-name allowlist / sanitize (#6)."""

from __future__ import annotations

import unittest
from unittest import mock

from appgrid.helpers import apt_helper
from appgrid.helpers.apt_helper import check_packages, dispatch, is_safe_package_name, main
from appgrid.services.packagekit import _helper


class PackageNameAllowlistTests(unittest.TestCase):
    def test_accepts_debian_style_names(self) -> None:
        for name in (
            "firefox",
            "libgtk-3-0",
            "python3.12",
            "linux-image-6.8.0-40-generic",
            "foo:amd64",
            "bar+baz",
            "pkg~rc1",
            "a_b-c.d+e:f~g",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_safe_package_name(name))

    def test_refuses_shell_metacharacters_and_paths(self) -> None:
        for name in (
            "",
            "firefox;rm",
            "foo bar",
            "../evil",
            "/usr/bin/evil",
            "pkg$(reboot)",
            "pkg`id`",
            "pkg|cat",
            "pkg&true",
            "pkg>out",
            "pkg'quote",
            'pkg"quote',
            "pkg*",
            "pkg?",
            "pkg[0]",
            "pkg{a}",
            "pkg\nname",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_safe_package_name(name))

    def test_check_packages_raises_system_exit(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            check_packages(["ok-pkg", "bad;pkg"])
        self.assertIn("refusing unsafe package name", str(ctx.exception))

    def test_dispatch_refuses_unsafe_before_root_check(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            dispatch("install", ["safe", "bad pkg"])
        self.assertIn("refusing unsafe package name", str(ctx.exception))

    def test_main_prints_refusal_for_unsafe_name(self) -> None:
        with mock.patch("sys.stderr"):
            code = main(["install", "evil;rm"])
        self.assertEqual(code, 1)

    def test_helper_path_matches_policykit(self) -> None:
        """Only /usr/bin/appgrid-apt-helper is searched (PolicyKit annotate path)."""
        with mock.patch("os.path.isfile", return_value=False):
            self.assertIsNone(_helper())
        with mock.patch("os.path.isfile", side_effect=lambda p: p == "/usr/bin/appgrid-apt-helper"):
            with mock.patch("os.access", return_value=True):
                self.assertEqual(_helper(), "/usr/bin/appgrid-apt-helper")
        # Legacy /usr/libexec path must never be accepted.
        with mock.patch(
            "os.path.isfile",
            side_effect=lambda p: p == "/usr/libexec/appgrid/apt-helper",
        ):
            with mock.patch("os.access", return_value=True):
                self.assertIsNone(_helper())

    def test_unknown_action_refused(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            dispatch("purge", ["firefox"])
        self.assertIn("unknown action", str(ctx.exception))


class PackageKitFirstTests(unittest.TestCase):
    def test_refresh_and_upgrade_prefers_packagekit(self) -> None:
        from appgrid.services import packagekit

        calls: list[str] = []

        def fake_pkcon() -> str | None:
            return "/usr/bin/pkcon"

        def fake_helper() -> str | None:
            return "/usr/bin/appgrid-apt-helper"

        def fake_run(argv, env=None):  # noqa: ANN001
            calls.append(" ".join(argv))
            return ""

        with mock.patch.object(packagekit, "_pkcon", fake_pkcon):
            with mock.patch.object(packagekit, "_helper", fake_helper):
                with mock.patch.object(packagekit, "_run", fake_run):
                    with mock.patch.object(packagekit.progress, "report"):
                        packagekit.refresh_and_upgrade_system()
        self.assertEqual(len(calls), 1)
        self.assertIn("pkcon", calls[0])
        self.assertNotIn("appgrid-apt-helper", calls[0])

    def test_refresh_and_upgrade_falls_back_to_helper(self) -> None:
        from appgrid.services import packagekit

        helper_calls: list[tuple] = []

        def fake_run_helper(action: str, packages: list[str]) -> None:
            helper_calls.append((action, packages))

        with mock.patch.object(packagekit, "_pkcon", return_value=None):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                    with mock.patch.object(packagekit.progress, "report"):
                        packagekit.refresh_and_upgrade_system()
        self.assertEqual(helper_calls, [("refresh-upgrade", [])])


if __name__ == "__main__":
    unittest.main()
