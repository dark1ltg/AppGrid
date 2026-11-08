"""APT list --upgradable parse hardening (hunt-4 #9)."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from appgrid.backends.apt import AptBackend


def _result(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["apt"], 0, stdout, "")


class AptListParseTests(unittest.TestCase):
    def test_malformed_line_does_not_stamp_arch_as_version(self) -> None:
        backend = AptBackend()
        stdout = "pkg/jammy amd64 [upgradable from: 1.0]\n"
        with mock.patch("appgrid.backends.apt.run_capture", return_value=_result(stdout)):
            with mock.patch("appgrid.backends.apt.os.path.isfile", return_value=True):
                with mock.patch("appgrid.backends.apt.os.access", return_value=True):
                    candidates, names = backend._listed_upgrades()
        self.assertIn("pkg", names)
        self.assertNotIn("pkg", candidates)

    def test_normal_line_keeps_candidate_version(self) -> None:
        backend = AptBackend()
        stdout = (
            "firefox/jammy-updates 1:133.0+build1-0ubuntu0.22.04.1 amd64 "
            "[upgradable from: 1:132.0]\n"
        )
        with mock.patch("appgrid.backends.apt.run_capture", return_value=_result(stdout)):
            with mock.patch("appgrid.backends.apt.os.path.isfile", return_value=True):
                with mock.patch("appgrid.backends.apt.os.access", return_value=True):
                    candidates, names = backend._listed_upgrades()
        self.assertIn("firefox", names)
        self.assertEqual(candidates["firefox"], "1:133.0+build1-0ubuntu0.22.04.1")


if __name__ == "__main__":
    unittest.main()
