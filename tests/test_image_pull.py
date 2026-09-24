"""Tests for the ImagePullDialog — verify it pulls a Docker image and shows progress.

Run:  pytest tests/test_image_pull.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("GUI_MASTER_PASSWORD", "test-master-password")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QTimer, QEventLoop
from PyQt5.QtWidgets import QApplication, QProgressBar, QPushButton

from unittest.mock import patch

from gui.dialogs_image_pull import ImagePullDialog


class TestImagePullDialog(unittest.TestCase):
    """Test the ImagePullDialog pulls an image and displays progress."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_constructs(self):
        """Dialog instantiates with correct title and initial state."""
        dlg = ImagePullDialog("alpine:latest")
        self.assertIsNotNone(dlg)
        self.assertIn("alpine:latest", dlg.windowTitle())
        self.assertEqual(dlg.value(), 0)

    def test_progress_bar_exists(self):
        """Dialog contains a QProgressBar widget."""
        dlg = ImagePullDialog("alpine:latest")
        bar = dlg.findChild(QProgressBar)
        self.assertIsNotNone(bar, "QProgressBar not found in ImagePullDialog")

    def test_cancel_button_exists(self):
        """Dialog contains a cancel button."""
        dlg = ImagePullDialog("alpine:latest")
        # QProgressDialog creates a QPushButton labeled "Cancel"
        buttons = dlg.findChildren(QPushButton)
        cancel_btns = [b for b in buttons if b.text() == "Cancel"]
        self.assertTrue(
            len(cancel_btns) >= 1,
            "Cancel button not found in ImagePullDialog",
        )

    def test_pull_alpine_latest(self):
        """Pull alpine:latest and verify the dialog closes on completion."""
        dlg = ImagePullDialog("alpine:latest")

        # Track progress updates
        progress_values: list[int] = []
        finished_result: list[tuple[bool, str]] = []

        dlg._worker = None  # will be set by start_pull

        # Connect to the dialog's internal worker signals after start_pull
        original_start_pull = dlg.start_pull

        def wrapped_start_pull():
            original_start_pull()
            # Now the worker exists — connect to its signals
            if dlg._worker:
                dlg._worker.progress.connect(
                    lambda status, layer, pct, detail: progress_values.append(pct)
                )
                dlg._worker.finished.connect(
                    lambda success, msg: finished_result.append((success, msg))
                )

        dlg.start_pull = wrapped_start_pull

        # Start the pull
        dlg.start_pull()

        # Verify the worker thread is running
        self.assertIsNotNone(dlg._worker)
        self.assertTrue(dlg._worker.isRunning())

        # Wait for completion (max 60 seconds)
        loop = QEventLoop()
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.setInterval(60_000)  # 60s
        timeout_timer.timeout.connect(loop.quit)

        if dlg._worker:
            dlg._worker.finished.connect(loop.quit)

        timeout_timer.start()
        loop.exec_()

        # Verify the worker finished
        self.assertFalse(dlg._worker.isRunning())

        # Verify we got a result
        self.assertEqual(len(finished_result), 1, "Worker did not emit finished signal")
        success, message = finished_result[0]
        self.assertTrue(success, f"Pull failed: {message}")

        # Verify progress was reported (at least one update)
        self.assertGreater(len(progress_values), 0, "No progress updates received")

        # Verify the dialog closed
        self.assertFalse(dlg.isVisible())

        # Clean up the message box that _on_finished shows
        # (it's modal — auto-accept it)
        QTimer.singleShot(100, lambda: self._accept_top_level())
        # Process events briefly so the message box can be dismissed
        QApplication.processEvents()

    def _accept_top_level(self):
        """Dismiss any modal message box."""
        for widget in self.app.topLevelWidgets():
            if widget.isVisible() and widget.metaObject().className() == "QMessageBox":
                widget.accept()


if __name__ == "__main__":
    unittest.main()
