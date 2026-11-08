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

        def fake_run(argv, env=None):  # noqa: ANN001
            calls.append(" ".join(argv))
            return ""

        with mock.patch.object(
            packagekit, "_packagekit_cli", return_value=("/usr/bin/pkcon", "pkcon")
        ):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
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

        with mock.patch.object(packagekit, "_packagekit_cli", return_value=None):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                    with mock.patch.object(packagekit.progress, "report"):
                        packagekit.refresh_and_upgrade_system()
        self.assertEqual(helper_calls, [("refresh-upgrade", [])])

    def test_prefers_pkgcli_over_pkcon(self) -> None:
        from appgrid.services import packagekit

        def isfile(path: str) -> bool:
            return path in {"/usr/bin/pkgcli", "/usr/bin/pkcon"}

        with mock.patch.object(packagekit.shutil, "which", return_value=None):
            with mock.patch.object(packagekit.os.path, "isfile", side_effect=isfile):
                with mock.patch.object(packagekit.os, "access", return_value=True):
                    found = packagekit._packagekit_cli()
        self.assertEqual(found, ("/usr/bin/pkgcli", "pkgcli"))

    def test_pkcon_exit_5_with_packages_is_error(self) -> None:
        from appgrid.services import packagekit

        with mock.patch.object(
            packagekit, "run_streaming", return_value=(5, "Transaction failed: nothing useful to do")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                packagekit._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])
        self.assertIn("nothing useful", str(ctx.exception))

    def test_pkcon_exit_5_empty_install_is_plain_failure(self) -> None:
        from appgrid.services import packagekit

        with mock.patch.object(packagekit, "run_streaming", return_value=(5, "")):
            with self.assertRaises(RuntimeError) as ctx:
                packagekit._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])
        # Blank output is a plain PackageKit fail — not auth / helper bait (hunt-4 #2).
        text = str(ctx.exception).lower()
        self.assertIn("packagekit", text)
        self.assertNotIn("authorization", text)

    def test_pkcon_exit_5_refresh_noop_ok(self) -> None:
        from appgrid.services import packagekit

        with mock.patch.object(
            packagekit, "run_streaming", return_value=(5, "Nothing useful to do.")
        ):
            out = packagekit._run(["/usr/bin/pkcon", "--plain", "-y", "refresh"])
        self.assertIn("Nothing useful", out)

    def test_auth_cancel_message(self) -> None:
        from appgrid.services import packagekit
        from appgrid.services.jobs import CancelledError

        with mock.patch.object(
            packagekit, "run_streaming", return_value=(1, "Error: The authentication was dismissed.")
        ):
            with self.assertRaises(CancelledError) as ctx:
                packagekit._run(["/usr/bin/pkgcli", "--yes", "install", "hello"])
        self.assertIn("permission", str(ctx.exception).lower())


class StickyStatusTests(unittest.TestCase):
    def test_post_action_reload_does_not_clear_via_reload(self) -> None:
        """Post-action refresh must call _reload(False), not reload() (clears sticky)."""
        from pathlib import Path

        src = Path("appgrid/controller.py").read_text(encoding="utf-8")
        # Isolate _reload_after_action body.
        start = src.index("def _reload_after_action")
        end = src.index("\n    @Slot()", start)
        body = src[start:end]
        self.assertIn("self._reload(False)", body)
        self.assertNotIn("self.reload()", body)

    def test_apply_catalog_keeps_pending_status(self) -> None:
        from pathlib import Path

        src = Path("appgrid/controller.py").read_text(encoding="utf-8")
        start = src.index("def _apply_catalog")
        end = src.index("\n    def _clear_pending_status", start)
        body = src[start:end]
        self.assertIn("self._pending_status", body)
        self.assertNotIn("self._pending_status = None", body)
        self.assertIn("_clear_pending_status", body)


class PolkitSessionTests(unittest.TestCase):
    def test_popen_does_not_start_new_session(self) -> None:
        """setsid/start_new_session breaks polkit password dialogs."""
        import inspect

        from appgrid.services import jobs

        src = inspect.getsource(jobs._popen)
        self.assertIn("start_new_session=False", src)
        self.assertIn("preexec_fn", src)
        self.assertNotIn("start_new_session=True", src)

    def test_auth_failure_falls_back_to_helper(self) -> None:
        from appgrid.services import packagekit

        helper_calls: list[tuple] = []

        def fake_run_packagekit(verb: str, packages: list[str] | None = None) -> None:
            raise RuntimeError("Failed to obtain authorization")

        def fake_run_helper(action: str, packages: list[str]) -> None:
            helper_calls.append((action, list(packages)))

        with mock.patch.object(
            packagekit, "_packagekit_cli", return_value=("/usr/bin/pkgcli", "pkgcli")
        ):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_packagekit", fake_run_packagekit):
                    with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                        with mock.patch.object(packagekit.progress, "report"):
                            packagekit._one_auth_path(
                                "install", ["hello"], "install", ["install", "-y", "hello"]
                            )
        self.assertEqual(helper_calls, [("install", ["hello"])])

    def test_wrong_password_does_not_fall_back_to_helper(self) -> None:
        from appgrid.services import packagekit

        helper_calls: list[tuple] = []

        def fake_run_packagekit(verb: str, packages: list[str] | None = None) -> None:
            raise RuntimeError("Authentication failed: incorrect password")

        def fake_run_helper(action: str, packages: list[str]) -> None:
            helper_calls.append((action, list(packages)))

        with mock.patch.object(
            packagekit, "_packagekit_cli", return_value=("/usr/bin/pkgcli", "pkgcli")
        ):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_packagekit", fake_run_packagekit):
                    with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                        with mock.patch.object(packagekit.progress, "report"):
                            with self.assertRaises(RuntimeError):
                                packagekit._one_auth_path(
                                    "install", ["hello"], "install", ["install", "-y", "hello"]
                                )
        self.assertEqual(helper_calls, [])

    def test_empty_pk_failure_does_not_fall_back_to_helper(self) -> None:
        """Blank/generic PK fail must not open a second pkexec dialog (hunt-4 #2)."""
        from appgrid.services import packagekit

        helper_calls: list[tuple] = []

        def fake_run_packagekit(verb: str, packages: list[str] | None = None) -> None:
            raise RuntimeError("PackageKit failed (exit 1)")

        def fake_run_helper(action: str, packages: list[str]) -> None:
            helper_calls.append((action, list(packages)))

        with mock.patch.object(
            packagekit, "_packagekit_cli", return_value=("/usr/bin/pkgcli", "pkgcli")
        ):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_packagekit", fake_run_packagekit):
                    with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                        with mock.patch.object(packagekit.progress, "report"):
                            with self.assertRaises(RuntimeError):
                                packagekit.refresh_and_upgrade_system()
        self.assertEqual(helper_calls, [])

    def test_refresh_indexes_falls_back_to_helper(self) -> None:
        from appgrid.services import packagekit

        helper_calls: list[tuple] = []

        def fake_run_packagekit(verb: str, packages: list[str] | None = None) -> None:
            raise RuntimeError("Failed to obtain authorization. No password dialog appeared.")

        def fake_run_helper(action: str, packages: list[str]) -> None:
            helper_calls.append((action, list(packages)))

        with mock.patch.object(
            packagekit, "_packagekit_cli", return_value=("/usr/bin/pkcon", "pkcon")
        ):
            with mock.patch.object(packagekit, "_helper", return_value="/usr/bin/appgrid-apt-helper"):
                with mock.patch.object(packagekit, "_run_packagekit", fake_run_packagekit):
                    with mock.patch.object(packagekit, "_run_helper", fake_run_helper):
                        with mock.patch.object(packagekit.progress, "report"):
                            packagekit.refresh_package_indexes()
        self.assertEqual(helper_calls, [("refresh", [])])


if __name__ == "__main__":
    unittest.main()
