"""Unit tests for PackageKit argv, exit-5 / noop, and auth helpers (hunt-4/5)."""

from __future__ import annotations

import unittest
from unittest import mock

from appgrid.services import packagekit as pk
from appgrid.services.jobs import CancelledError


class PkArgvTests(unittest.TestCase):
    def test_update_system_uses_cache_age_equals(self) -> None:
        with mock.patch.object(pk, "_packagekit_cli", return_value=("/usr/bin/pkcon", "pkcon")):
            argv = pk._pk_argv("update-system")
        self.assertEqual(argv[-2:], ["--cache-age=0", "update"])
        self.assertNotIn("0", argv[1:-1])  # bare 0 must not be positional (#5)

    def test_verb_parse_skips_numeric_cache_age(self) -> None:
        # Legacy form still parses if someone rebuilds with split --cache-age 0.
        verb, packages = pk._pk_verb_and_packages(
            ["/usr/bin/pkcon", "--plain", "-y", "--cache-age", "0", "update"]
        )
        self.assertEqual(verb, "update")
        self.assertEqual(packages, [])

    def test_verb_parse_equals_form(self) -> None:
        verb, packages = pk._pk_verb_and_packages(
            ["/usr/bin/pkcon", "--plain", "-y", "--cache-age=0", "update"]
        )
        self.assertEqual(verb, "update")
        self.assertEqual(packages, [])


class NoopAndAuthTests(unittest.TestCase):
    def test_noop_text_excludes_bare_already_and_bare_no_packages(self) -> None:
        self.assertNotIn("already", pk._NOOP_TEXT)
        self.assertNotIn("no packages", pk._NOOP_TEXT)
        self.assertTrue(any("no packages require" in t for t in pk._NOOP_TEXT))
        self.assertTrue(any("up-to-date" in t or "up to date" in t for t in pk._NOOP_TEXT))

    def test_error_no_packages_were_found_is_not_noop_success(self) -> None:
        with mock.patch.object(
            pk, "run_streaming", return_value=(5, "Error: no packages were found")
        ):
            with self.assertRaises(RuntimeError):
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "--cache-age=0", "update"])

    def test_refresh_fatal_exit5_fails_closed(self) -> None:
        with mock.patch.object(
            pk,
            "run_streaming",
            return_value=(5, "Fatal error: Failed to download repository information"),
        ):
            with self.assertRaises(RuntimeError):
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "refresh"])

    def test_refresh_noop_still_ok(self) -> None:
        with mock.patch.object(
            pk, "run_streaming", return_value=(5, "Nothing useful to do.")
        ):
            out = pk._run(["/usr/bin/pkcon", "--plain", "-y", "refresh"])
        self.assertIn("Nothing useful", out)

    def test_pkgcli_exit5_noop_ok(self) -> None:
        with mock.patch.object(
            pk, "run_streaming", return_value=(5, "Nothing useful to do.")
        ):
            out = pk._run(["/usr/bin/pkgcli", "--yes", "update"])
        self.assertIn("Nothing useful", out)

    def test_blank_authish_exit_is_helper_fallback(self) -> None:
        with mock.patch.object(pk, "run_streaming", return_value=(1, "")):
            with self.assertRaises(RuntimeError) as ctx:
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])
        self.assertTrue(pk._looks_helper_fallback(str(ctx.exception)))
        self.assertIn("try again", str(ctx.exception).lower())

    def test_blank_exit5_is_plain_failure(self) -> None:
        with mock.patch.object(pk, "run_streaming", return_value=(5, "")):
            with self.assertRaises(RuntimeError) as ctx:
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])
        text = str(ctx.exception).lower()
        self.assertIn("packagekit", text)
        self.assertFalse(pk._looks_helper_fallback(str(ctx.exception)))

    def test_blank_string_alone_is_not_helper_fallback(self) -> None:
        self.assertFalse(pk._looks_helper_fallback(""))
        self.assertFalse(pk._looks_helper_fallback("   "))

    def test_no_agent_is_helper_fallback(self) -> None:
        self.assertTrue(
            pk._looks_helper_fallback("Failed to obtain authorization; no agent is available")
        )

    def test_wrong_password_is_not_helper_fallback(self) -> None:
        self.assertFalse(pk._looks_helper_fallback("Authentication failed: incorrect password"))

    def test_busy_locked_exit5_raises(self) -> None:
        with mock.patch.object(pk, "run_streaming", return_value=(5, "Transaction already running")):
            with self.assertRaises(RuntimeError) as ctx:
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "--cache-age=0", "update"])
        text = str(ctx.exception).lower()
        self.assertTrue("busy" in text or "already running" in text)

    def test_not_authorized_is_auth_not_cancel(self) -> None:
        with mock.patch.object(
            pk, "run_streaming", return_value=(1, "GDBus: not authorized to perform operation")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])
        self.assertNotIsInstance(ctx.exception, CancelledError)
        self.assertTrue(pk._looks_helper_fallback(str(ctx.exception)))

    def test_dismissed_still_cancels(self) -> None:
        with mock.patch.object(
            pk, "run_streaming", return_value=(1, "Error: The authentication was dismissed.")
        ):
            with self.assertRaises(CancelledError):
                pk._run(["/usr/bin/pkcon", "--plain", "-y", "install", "hello"])

    def test_auth_copy_says_try_again_not_install(self) -> None:
        msg = pk._auth_fail_message("no agent is available", 1)
        self.assertIn("try again", msg.lower())
        self.assertNotIn("try Install again", msg)


if __name__ == "__main__":
    unittest.main()
