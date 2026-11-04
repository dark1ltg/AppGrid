"""Unit tests for progress percent extraction and grace window (#2)."""

from __future__ import annotations

import unittest
from unittest import mock

from appgrid.services import progress


class ProgressPercentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines: list[str] = []
        self.percents: list[int] = []
        progress.set_reporter(self.lines.append, self.percents.append)

    def tearDown(self) -> None:
        progress.set_reporter(None)

    def test_extracts_pkcon_style_percent(self) -> None:
        self.assertEqual(progress.extract_percent("Downloaded 42%"), 42)
        self.assertEqual(progress.extract_percent("Progress: 88%"), 88)
        self.assertEqual(progress.extract_percent("[ 75% ]"), 75)
        self.assertEqual(progress.extract_percent("Installing… 10% complete"), 10)

    def test_ignores_non_progress_percent(self) -> None:
        self.assertIsNone(progress.extract_percent("battery at 5%"))
        self.assertIsNone(progress.extract_percent("version 3.0% leftover"))
        self.assertIsNone(progress.extract_percent("no percent here"))

    def test_report_publishes_percent(self) -> None:
        progress.report("Downloading packages… Progress: 33%")
        self.assertEqual(self.percents[-1], 33)
        self.assertTrue(self.lines)

    def test_grace_window_keeps_last_percent(self) -> None:
        clock = {"t": 100.0}

        def mono() -> float:
            return clock["t"]

        with mock.patch("appgrid.services.progress.time.monotonic", mono):
            progress.report("Progress: 50%")
            self.assertEqual(self.percents[-1], 50)
            clock["t"] = 100.5  # within 1.5s grace
            progress.report("Unpacking firefox…")
            self.assertEqual(self.percents[-1], 50)
            clock["t"] = 102.0  # past grace
            progress.report("Setting up firefox…")
            self.assertEqual(self.percents[-1], -1)


if __name__ == "__main__":
    unittest.main()
