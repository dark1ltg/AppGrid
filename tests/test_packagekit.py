"""Unit tests for PackageKit argv parse and exit-5 / auth helpers (hunt-4)."""

from __future__ import annotations

import unittest
from unittest import mock

from appgrid.services import packagekit as pk


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
    def test_noop_text_excludes_bare_already(self) -> None:
        self.assertNotIn("already", pk._NOOP_TEXT)
        self.assertTrue(any("up-to-date" in t or "up to date" in t for t in pk._NOOP_TEXT))

    def test_blank_output_is_not_helper_fallback(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
